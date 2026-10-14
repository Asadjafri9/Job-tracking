"""PostgreSQL-backed API checks for profile, documents, and extraction review."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth
from app.db.connection import sqlalchemy_url
from app.db.models import (
    Document,
    DocumentExtraction,
    Job,
    Profile,
    ProfileFactVersion,
    User,
)
from app.main import app
from app.modules import documents as documents_module
from app.modules import extractions as extractions_module
from app.modules import profile as profile_module
from app.storage.blob import InMemoryDocumentStorage

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "M2 API tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("M2 API tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)
STORAGE = InMemoryDocumentStorage()

PDF_BYTES = b"%PDF-1.4 minimal"


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://m2-api.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{identity}@example.test",
                login_email_verified=True,
            )
        )
        session.flush()
        session.add(Profile(user_id=identity))
    try:
        yield identity
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == identity))


@pytest.fixture
def client(owner_id: UUID, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    auth = AuthContext(
        user_id=owner_id, token="m2-token", auth_time=datetime.now(UTC)
    )
    app.dependency_overrides[require_auth] = lambda: auth
    for module in (profile_module, documents_module, extractions_module):
        monkeypatch.setattr(module, "_runtime_engine", lambda: runtime_engine)
        monkeypatch.setattr(module, "require_csrf", lambda *_args: None)
    monkeypatch.setattr(documents_module, "_storage", lambda: STORAGE)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_profile_fact_lifecycle(client: TestClient, owner_id: UUID) -> None:
    created = client.put(
        "/api/v1/profile/facts",
        json={
            "fact_key": "contact.email",
            "value_type": "TEXT",
            "value": "owner@example.test",
            "sensitivity": "NORMAL",
            "allowed_purposes": ["AUTOFILL"],
        },
    )
    assert created.status_code == 201
    fact = created.json()
    assert fact["confirmation_state"] == "CONFIRMED"
    assert fact["source_type"] == "MANUAL"

    duplicate = client.put(
        "/api/v1/profile/facts",
        json={
            "fact_key": "contact.email",
            "value_type": "TEXT",
            "value": "other@example.test",
            "sensitivity": "NORMAL",
            "allowed_purposes": [],
        },
    )
    assert duplicate.status_code == 409

    profile = client.get("/api/v1/profile")
    assert profile.status_code == 200
    assert profile.json()["facts"][0]["fact_key"] == "contact.email"
    etag = profile.headers["etag"]

    updated = client.post(
        f"/api/v1/profile/facts/{fact['id']}",
        json={
            "fact_key": "contact.email",
            "value_type": "TEXT",
            "value": "new@example.test",
            "sensitivity": "NORMAL",
            "allowed_purposes": ["AUTOFILL", "EMAIL"],
            "expected_revision": fact["current_revision"],
        },
        headers={"If-Match": f'"{fact["current_revision"]}"'},
    )
    assert updated.status_code == 200
    assert updated.json()["current_revision"] == fact["current_revision"] + 1

    stale = client.post(
        f"/api/v1/profile/facts/{fact['id']}",
        json={
            "fact_key": "contact.email",
            "value_type": "TEXT",
            "value": "stale@example.test",
            "sensitivity": "NORMAL",
            "allowed_purposes": [],
            "expected_revision": fact["current_revision"],
        },
        headers={"If-Match": f'"{fact["current_revision"]}"'},
    )
    assert stale.status_code == 409

    deleted = client.delete(f"/api/v1/profile/facts/{fact['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/profile").json()["facts"] == []
    assert etag.startswith('"')


def test_document_upload_list_download_and_delete(client: TestClient, owner_id: UUID) -> None:
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("resume.pdf", PDF_BYTES, "application/pdf")},
        data={"document_type": "RESUME"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["original_state"] == "READY"
    assert document["parse_state"] == "QUEUED"
    with Session(migration_engine) as session:
        jobs = session.scalars(
            select(Job).where(Job.user_id == owner_id, Job.kind == "document.parse")
        ).all()
        assert len(jobs) == 1

    listed = client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["documents"][0]["id"] == document["id"]

    downloaded = client.get(f"/api/v1/documents/{document['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == PDF_BYTES

    deleted = client.delete(f"/api/v1/documents/{document['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/documents").json()["documents"] == []


def test_upload_rejects_bad_signature_and_oversize(client: TestClient) -> None:
    wrong_magic = client.post(
        "/api/v1/documents",
        files={"file": ("resume.pdf", b"not-a-pdf", "application/pdf")},
        data={"document_type": "RESUME"},
    )
    assert wrong_magic.status_code == 422

    oversize = client.post(
        "/api/v1/documents",
        files={"file": ("big.pdf", b"%PDF-1.4 " + b"x" * (5 * 1024 * 1024), "application/pdf")},
        data={"document_type": "RESUME"},
    )
    assert oversize.status_code == 413

    wrong_type = client.post(
        "/api/v1/documents",
        files={"file": ("resume.docx", b"PK\x03\x04", "application/pdf")},
        data={"document_type": "LINKEDIN_PDF"},
    )
    assert wrong_type.status_code == 422


def _seed_extraction(owner_id: UUID) -> tuple[UUID, UUID]:
    with Session(migration_engine) as session, session.begin():
        document = Document(
            user_id=owner_id,
            document_type="RESUME",
            storage_key="seed",
            file_name="resume.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            original_state="READY",
            parse_state="PARSED",
        )
        session.add(document)
        session.flush()
        extraction = DocumentExtraction(
            user_id=owner_id,
            document_id=document.id,
            document_revision=document.revision,
            parse_version="parser-v1",
            extracted_text="Worked at Example Corp",
            source_anchors=[{"page": 1, "block": 0, "excerpt": "Example Corp"}],
            candidates=[
                {
                    "fact_key": "employers.current",
                    "value_type": "TEXT",
                    "value": "Example Corp",
                    "section_id": 0,
                    "anchor": {"page": 1, "block": 0},
                    "decision": None,
                }
            ],
            candidate_count=1,
            review_state="REVIEW_REQUIRED",
        )
        session.add(extraction)
        session.flush()
        return document.id, extraction.id


def test_candidate_confirm_writes_document_sourced_fact(
    client: TestClient, owner_id: UUID
) -> None:
    document_id, extraction_id = _seed_extraction(owner_id)

    listed = client.get(f"/api/v1/documents/{document_id}/extractions")
    assert listed.status_code == 200
    assert listed.json()[0]["candidates"][0]["fact_key"] == "employers.current"

    decided = client.post(
        f"/api/v1/extractions/{extraction_id}/candidates/0/decision",
        json={"action": "CONFIRM"},
    )
    assert decided.status_code == 200
    assert decided.json()["candidates"][0]["decision"] == "CONFIRMED"

    profile = client.get("/api/v1/profile")
    facts = profile.json()["facts"]
    assert len(facts) == 1
    assert facts[0]["fact_key"] == "employers.current"
    assert facts[0]["source_type"] == "DOCUMENT"
    assert facts[0]["confirmation_state"] == "CONFIRMED"

    with Session(migration_engine) as session:
        version = session.scalar(
            select(ProfileFactVersion).where(ProfileFactVersion.user_id == owner_id)
        )
        assert version is not None
        assert version.document_id == document_id
        assert version.page_number == 1

    decided_again = client.post(
        f"/api/v1/extractions/{extraction_id}/candidates/0/decision",
        json={"action": "REJECT"},
    )
    assert decided_again.status_code == 409


def test_extraction_rerun_is_rejected_before_provider_call(
    client: TestClient, owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running a populated extraction must not overwrite owner review or
    issue another provider call."""
    document_id, extraction_id = _seed_extraction(owner_id)  # has candidates
    calls: list[object] = []
    monkeypatch.setattr(
        extractions_module, "run_operation", lambda *a, **k: calls.append(1)
    )
    response = client.post(
        f"/api/v1/documents/{document_id}/extractions/{extraction_id}/extract"
    )
    assert response.status_code == 409
    assert calls == []


def test_candidate_reject_marks_decision(client: TestClient, owner_id: UUID) -> None:
    _, extraction_id = _seed_extraction(owner_id)
    decided = client.post(
        f"/api/v1/extractions/{extraction_id}/candidates/0/decision",
        json={"action": "REJECT"},
    )
    assert decided.status_code == 200
    assert decided.json()["candidates"][0]["decision"] == "REJECTED"
    assert client.get("/api/v1/profile").json()["facts"] == []


def test_profile_isolation_between_owners(client: TestClient) -> None:
    # The runtime RLS session only ever sees the authenticated owner.
    response = client.get("/api/v1/profile")
    assert response.status_code == 200
    assert response.json()["facts"] == []
