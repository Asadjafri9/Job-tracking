"""PostgreSQL-backed checks for exports and staged account deletion (M6)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth
from app.db.connection import sqlalchemy_url
from app.db.jobs import enqueue_job
from app.db.models import (
    DeletionJournal,
    Document,
    ExportArtifact,
    Job,
    MonitoredSource,
    Profile,
    ProfileFact,
    ProviderCredential,
    User,
)
from app.db.models import Session as SessionRecord
from app.db.tenant import tenant_session
from app.main import app
from app.modules import privacy as privacy_module
from app.worker import handlers as worker_handlers
from app.worker.registry import JobContext

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "M6 API tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("M6 API tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://m6-api.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{identity}@example.test",
                login_email_verified=True,
            )
        )
        session.flush()
        session.add(Profile(user_id=identity, current_revision=1))
    try:
        yield identity
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == identity))


@pytest.fixture
def client(owner_id: UUID, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    auth = AuthContext(user_id=owner_id, token="m6-token", auth_time=datetime.now(UTC))
    app.dependency_overrides[require_auth] = lambda: auth
    monkeypatch.setattr(privacy_module, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(privacy_module, "require_csrf", lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_export_request_is_idempotent_while_building(client: TestClient) -> None:
    first = client.post("/api/v1/export-requests", json={})
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/export-requests", json={})
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    listing = client.get("/api/v1/export-requests")
    assert listing.status_code == 200
    assert len(listing.json()["exports"]) == 1
    assert listing.json()["exports"][0]["state"] == "BUILDING"


def test_export_download_requires_ready_artifact(
    client: TestClient, owner_id: UUID
) -> None:
    response = client.post("/api/v1/export-requests", json={})
    artifact_id = response.json()["id"]
    missing = client.get(f"/api/v1/export-requests/{artifact_id}/download")
    assert missing.status_code == 410


def test_export_isolation(client: TestClient, owner_id: UUID) -> None:
    other = uuid4()
    response = client.get(f"/api/v1/export-requests/{other}/download")
    assert response.status_code == 404


def _context(owner: UUID, reference_id: UUID | None = None) -> JobContext:
    return JobContext(
        id=uuid4(),
        owner_id=owner,
        kind="privacy.export",
        reference_type="export_artifact",
        reference_id=reference_id,
        attempt=1,
    )


def test_export_handler_publishes_artifact(
    client: TestClient, owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_handlers, "_runtime_engine", lambda: runtime_engine)
    blobs: dict[str, bytes] = {}
    monkeypatch.setattr(
        worker_handlers,
        "_document_storage",
        lambda: _MemoryStorage(blobs),
    )
    response = client.post("/api/v1/export-requests", json={})
    artifact_id = UUID(response.json()["id"])
    asyncio.run(
        worker_handlers.handle_export(
            _context(owner_id, artifact_id), asyncio.Event()
        )
    )
    assert blobs, "export blob was not written"
    listing = client.get("/api/v1/export-requests").json()["exports"]
    assert listing[0]["state"] == "READY"
    assert listing[0]["ready"] is True
    with zipfile.ZipFile(io.BytesIO(next(iter(blobs.values())))) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        facts = json.loads(archive.read("data/profile_facts.json"))
    assert manifest["schema_version"] == 2
    assert facts == []


class _MemoryStorage:
    """Matches BlobDocumentStorage: put fails when the key exists."""

    def __init__(self, blobs: dict[str, bytes]) -> None:
        self._blobs = blobs

    def put(self, key: str, data: bytes, content_type: str) -> None:
        if key in self._blobs:
            raise worker_handlers.StorageError("blob exists")
        self._blobs[key] = data

    def get(self, key: str) -> bytes:
        return self._blobs[key]

    def delete(self, key: str) -> None:
        self._blobs.pop(key, None)


def test_export_handler_retry_accepts_identical_blob(
    client: TestClient, owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry after a crash must publish when the blob is already there."""
    monkeypatch.setattr(worker_handlers, "_runtime_engine", lambda: runtime_engine)
    blobs: dict[str, bytes] = {}
    storage = _MemoryStorage(blobs)
    monkeypatch.setattr(
        worker_handlers, "_document_storage", lambda: storage
    )
    response = client.post("/api/v1/export-requests", json={})
    artifact_id = UUID(response.json()["id"])
    key = f"exports/{owner_id}/{artifact_id}.zip"
    asyncio.run(
        worker_handlers.handle_export(
            _context(owner_id, artifact_id), asyncio.Event()
        )
    )
    # Simulate a crash after commit... no: after put, before publish. Reset
    # the artifact to BUILDING while keeping the blob.
    with tenant_session(runtime_engine, owner_id) as session:
        artifact = session.get(ExportArtifact, artifact_id)
        assert artifact is not None
        artifact.state = "BUILDING"
        artifact.storage_key = None
        artifact.sha256 = None
    asyncio.run(
        worker_handlers.handle_export(
            _context(owner_id, artifact_id), asyncio.Event()
        )
    )
    with tenant_session(runtime_engine, owner_id) as session:
        artifact = session.get(ExportArtifact, artifact_id)
        assert artifact is not None
        assert artifact.state == "READY"
        assert artifact.storage_key == key


def test_export_handler_drops_artifact_for_non_active_owner(
    owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_handlers, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(
        worker_handlers, "_document_storage", lambda: _MemoryStorage({})
    )
    with tenant_session(runtime_engine, owner_id) as session:
        job = enqueue_job(
            session,
            owner_id=owner_id,
            kind="privacy.export",
            reference_type="export_artifact",
        )
        artifact = ExportArtifact(
            user_id=owner_id,
            job_id=job.id,
            state="BUILDING",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        session.add(artifact)
        session.flush()
        artifact_id = artifact.id
        session.execute(
            sa.text("SELECT copilot_begin_deletion()")
        )

    asyncio.run(
        worker_handlers.handle_export(
            _context(owner_id, artifact_id), asyncio.Event()
        )
    )
    with tenant_session(runtime_engine, owner_id) as session:
        artifact = session.get(ExportArtifact, artifact_id)
        assert artifact is not None
        assert artifact.state == "DELETED"
        assert artifact.storage_key is None


def test_account_deletion_requires_fresh_auth(
    owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = AuthContext(
        user_id=owner_id,
        token="m6-stale",
        auth_time=datetime.now(UTC) - timedelta(minutes=30),
    )
    app.dependency_overrides[require_auth] = lambda: stale
    monkeypatch.setattr(privacy_module, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(privacy_module, "require_csrf", lambda *_args: None)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/account/deletion", json={"confirmation": "DELETE"}
        )
        assert response.status_code == 403
    app.dependency_overrides.clear()


def test_account_deletion_rejects_wrong_confirmation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/account/deletion", json={"confirmation": "delete"}
    )
    assert response.status_code == 422


def test_account_deletion_revokes_and_journals(
    client: TestClient, owner_id: UUID
) -> None:
    with tenant_session(runtime_engine, owner_id) as session:
        session.add(
            SessionRecord(
                user_id=owner_id,
                token_hash="a" * 64,
                auth_time=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        session.add(
            ProviderCredential(
                user_id=owner_id,
                provider="OPENROUTER",
                ciphertext=b"cipher",
                nonce=b"nonce",
                wrapped_dek=b"dek",
                kek_version="local-test",
                key_last4="1234",
                enabled=True,
                status="READY",
            )
        )
        session.add(
            MonitoredSource(
                user_id=owner_id,
                public_url="https://m6.example.com/jobs",
                source_kind="HTML",
                timezone="UTC",
                schedule="DAILY",
                state="ACTIVE",
                scheduled_check_consented_at=datetime.now(UTC),
                consent_revision=1,
                next_run_at=datetime.now(UTC),
            )
        )
        session.add(
            ProfileFact(
                user_id=owner_id,
                profile_id=session.scalar(
                    select(Profile.id).where(Profile.user_id == owner_id)
                ),
                fact_key="full_name",
                value_type="TEXT",
                value="Ada",
                allowed_purposes=["AUTOFILL"],
            )
        )
        enqueue_job(session, owner_id=owner_id, kind="maintenance.owner_cleanup")
    response = client.post(
        "/api/v1/account/deletion", json={"confirmation": "DELETE"}
    )
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["state"] == "DELETING"
    assert len(receipt["journal_hmac"]) == 64

    owner_hash = hashlib.sha256(str(owner_id).encode()).hexdigest()
    with tenant_session(runtime_engine, owner_id) as session:
        journal = session.scalar(
            select(DeletionJournal).where(
                DeletionJournal.user_id_hash == owner_hash
            )
        )
        assert journal is not None
        assert journal.revoked_credential_versions
        assert journal.revoked_session_digest is not None
        assert session.scalar(
            select(SessionRecord).where(
                SessionRecord.user_id == owner_id,
                SessionRecord.revoked_at.is_(None),
            )
        ) is None
        credential = session.scalar(
            select(ProviderCredential).where(
                ProviderCredential.user_id == owner_id
            )
        )
        assert credential is not None
        assert credential.status == "REVOKED"
        assert credential.ciphertext == b""
        source = session.scalar(
            select(MonitoredSource).where(MonitoredSource.user_id == owner_id)
        )
        assert source is not None
        assert source.state == "DELETED"
        assert source.next_run_at is None
        queued = session.scalar(
            select(Job).where(
                Job.user_id == owner_id,
                Job.state == "QUEUED",
            )
        )
        assert queued is None or queued.kind == "privacy.account_delete"

        # Stage 2 idempotency: a second request must not double-delete.
        again = client.post(
            "/api/v1/account/deletion", json={"confirmation": "DELETE"}
        )
        assert again.status_code == 409

        # Late results cannot repopulate: an export request after DELETING.
        export = client.post("/api/v1/export-requests", json={})
        assert export.status_code == 409


def test_account_delete_handler_erases_owned_data(
    client: TestClient, owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_handlers, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(
        worker_handlers, "_document_storage", lambda: _MemoryStorage({})
    )
    with tenant_session(runtime_engine, owner_id) as session:
        session.add(
            Document(
                user_id=owner_id,
                document_type="RESUME",
                storage_key=f"m6/{owner_id}/resume.pdf",
                file_name="resume.pdf",
                media_type="application/pdf",
                sha256="c" * 64,
                size_bytes=100,
                original_state="READY",
            )
        )
    client.post("/api/v1/account/deletion", json={"confirmation": "DELETE"})

    asyncio.run(
        worker_handlers.handle_account_delete(
            JobContext(
                id=uuid4(),
                owner_id=owner_id,
                kind="privacy.account_delete",
                reference_type=None,
                reference_id=None,
                attempt=1,
            ),
            asyncio.Event(),
        )
    )
    with tenant_session(runtime_engine, owner_id) as session:
        for model in (Document, Profile, ProfileFact, Job, ExportArtifact):
            assert session.scalar(select(model).where(model.user_id == owner_id)) is None
        state = session.scalar(
            sa.text("SELECT state FROM copilot_current_user LIMIT 1")
        )
        assert state == "DELETED"
    with migration_engine.begin() as connection:
        row = connection.execute(
            sa.text("SELECT state, login_email FROM users WHERE id = :id"),
            {"id": owner_id},
        ).one()
        assert row.state == "DELETED"
        assert row.login_email.startswith("deleted-")
        assert "@example.test" not in row.login_email


class _FailingDeleteStorage(_MemoryStorage):
    def delete(self, key: str) -> None:
        raise worker_handlers.StorageError("backend unavailable")


def test_account_delete_retries_when_blob_delete_fails(
    client: TestClient, owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A blob-delete failure must retry the job and leave rows for the retry,
    never delete DB rows while blobs remain orphaned."""
    monkeypatch.setattr(worker_handlers, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(
        worker_handlers, "_document_storage", lambda: _FailingDeleteStorage({})
    )
    with tenant_session(runtime_engine, owner_id) as session:
        session.add(
            Document(
                user_id=owner_id,
                document_type="RESUME",
                storage_key=f"m6/{owner_id}/resume.pdf",
                file_name="resume.pdf",
                media_type="application/pdf",
                sha256="c" * 64,
                size_bytes=100,
                original_state="READY",
            )
        )
    client.post("/api/v1/account/deletion", json={"confirmation": "DELETE"})

    with pytest.raises(worker_handlers.StorageError):
        asyncio.run(
            worker_handlers.handle_account_delete(
                JobContext(
                    id=uuid4(),
                    owner_id=owner_id,
                    kind="privacy.account_delete",
                    reference_type=None,
                    reference_id=None,
                    attempt=1,
                ),
                asyncio.Event(),
            )
        )
    # delete_data never ran: owned rows survive for the retried attempt.
    with tenant_session(runtime_engine, owner_id) as session:
        assert (
            session.scalar(select(Document).where(Document.user_id == owner_id))
            is not None
        )
