"""Privacy lifecycle: exports and staged account deletion (DATA-002/003).

Exports are durable jobs producing one private ZIP artifact with a 24-hour
download window; concurrent requests reuse the in-flight build. Account
deletion requires fresh authentication plus typed consent, writes the
independent content-free journal BEFORE acknowledgement, immediately
revokes sessions/credentials/schedules/jobs, and completes through a
staged worker job. Deletion is idempotent on the journal's user hash.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.jobs import enqueue_job
from app.db.models import (
    DeletionJournal,
    ExportArtifact,
    Job,
    MonitoredSource,
    MonitoringRun,
    ProviderCredential,
)
from app.db.models import Session as SessionRecord
from app.db.tenant import tenant_session
from app.storage.blob import document_storage

router = APIRouter(prefix="/api/v1", tags=["privacy"])

EXPORT_JOB_KIND = "privacy.export"
EXPORT_JOB_REFERENCE = "export_artifact"
EXPORT_DOWNLOAD_TTL = timedelta(hours=24)
DELETE_JOB_KIND = "privacy.account_delete"
DELETE_CONFIRMATION = "DELETE"
FRESH_AUTH_WINDOW = timedelta(minutes=10)


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExportView(StrictModel):
    id: UUID
    state: str
    size_bytes: int
    sha256: str | None
    expires_at: datetime
    created_at: datetime
    ready: bool


class ExportList(StrictModel):
    exports: list[ExportView]


class DeleteRequest(StrictModel):
    confirmation: Literal["DELETE"] = Field(
        description="Type DELETE to confirm irreversible account deletion"
    )


class DeleteReceipt(StrictModel):
    operation_id: UUID | None
    state: str
    journal_hmac: str | None
    receipt_expires_at: datetime


def _export_view(row: ExportArtifact, now: datetime) -> ExportView:
    ready = row.state == "READY" and row.expires_at > now and row.storage_key is not None
    return ExportView(
        id=row.id,
        state=row.state,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        expires_at=row.expires_at,
        created_at=row.created_at,
        ready=ready,
    )


def _require_fresh_auth(auth: AuthContext) -> None:
    if datetime.now(UTC) - auth.auth_time > FRESH_AUTH_WINDOW:
        raise HTTPException(
            status_code=403,
            detail="account deletion needs authentication within the last 10 minutes",
        )


def _current_user_state(session: Session) -> str | None:
    state = session.scalar(
        sa.text("SELECT state FROM copilot_current_user LIMIT 1")
    )
    return state if isinstance(state, str) else None


@router.post("/export-requests", response_model=ExportView, status_code=201)
def request_export(
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> ExportView:
    require_csrf(request, auth)
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        # Serialize export requests per owner so concurrent calls observe
        # the same in-flight BUILDING artifact instead of enqueueing
        # duplicate jobs.
        session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:owner))"),
            {"owner": str(auth.user_id)},
        )
        if _current_user_state(session) != "ACTIVE":
            raise HTTPException(status_code=409, detail="account is not active")
        existing = session.scalar(
            select(ExportArtifact)
            .where(
                ExportArtifact.user_id == auth.user_id,
                ExportArtifact.state == "BUILDING",
            )
            .order_by(ExportArtifact.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            return _export_view(existing, now)
        job = enqueue_job(session, owner_id=auth.user_id, kind=EXPORT_JOB_KIND)
        artifact = ExportArtifact(
            user_id=auth.user_id,
            job_id=job.id,
            state="BUILDING",
            expires_at=now + EXPORT_DOWNLOAD_TTL,
        )
        session.add(artifact)
        session.flush()
        job.reference_type = EXPORT_JOB_REFERENCE
        job.reference_id = artifact.id
        return _export_view(artifact, now)


@router.get("/export-requests", response_model=ExportList)
def list_exports(auth: AuthContext = Depends(require_auth)) -> ExportList:
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        rows = session.scalars(
            select(ExportArtifact)
            .where(ExportArtifact.user_id == auth.user_id)
            .order_by(ExportArtifact.created_at.desc())
            .limit(20)
        ).all()
        return ExportList(exports=[_export_view(row, now) for row in rows])


@router.get("/export-requests/{export_id}/download")
def download_export(
    export_id: UUID, auth: AuthContext = Depends(require_auth)
) -> Response:
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(ExportArtifact).where(
                ExportArtifact.id == export_id,
                ExportArtifact.user_id == auth.user_id,
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="export not found")
        if row.state != "READY" or row.expires_at <= now or not row.storage_key:
            raise HTTPException(status_code=410, detail="export is no longer available")
        storage_key = row.storage_key
    blob = document_storage().get(storage_key)
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="rolevo-export-{export_id}.zip"'
        },
    )


@router.post("/account/deletion", response_model=DeleteReceipt, status_code=201)
def request_deletion(
    body: DeleteRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> DeleteReceipt:
    require_csrf(request, auth)
    _require_fresh_auth(auth)
    if body.confirmation != DELETE_CONFIRMATION:
        raise HTTPException(status_code=422, detail="confirmation must be DELETE")
    now = datetime.now(UTC)
    user_hash = hashlib.sha256(str(auth.user_id).encode()).hexdigest()
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        journal = session.scalar(
            select(DeletionJournal).where(DeletionJournal.user_id_hash == user_hash)
        )
        if journal is not None:
            raise HTTPException(
                status_code=409, detail="account deletion is already recorded"
            )
        # Stage 1: mark DELETING (row-locking update inside the security
        # definer function) and revoke access before the receipt.
        if not session.scalar(sa.text("SELECT copilot_begin_deletion()")):
            raise HTTPException(status_code=404, detail="account not found")
        credential_versions: list[str] = []
        for credential in session.scalars(
            select(ProviderCredential).where(ProviderCredential.user_id == auth.user_id)
        ):
            credential_versions.append(f"{credential.provider}:r{credential.revision}")
            credential.status = "REVOKED"
            credential.enabled = False
            credential.ciphertext = b""
            credential.nonce = b""
            credential.wrapped_dek = b""
            credential.revoked_at = now
        session_hashes = session.scalars(
            select(SessionRecord.token_hash).where(
                SessionRecord.user_id == auth.user_id,
                SessionRecord.revoked_at.is_(None),
            )
        ).all()
        session.execute(
            update(SessionRecord)
            .where(
                SessionRecord.user_id == auth.user_id,
                SessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        session.execute(
            update(MonitoredSource)
            .where(
                MonitoredSource.user_id == auth.user_id,
                MonitoredSource.state != "DELETED",
            )
            .values(state="DELETED", next_run_at=None)
        )
        session.execute(
            update(MonitoringRun)
            .where(
                MonitoringRun.user_id == auth.user_id,
                MonitoringRun.state == "QUEUED",
            )
            .values(state="CANCELED", redacted_error="account_deleting", ended_at=now)
        )
        session.execute(
            update(Job)
            .where(
                Job.user_id == auth.user_id,
                Job.state == "QUEUED",
            )
            .values(state="CANCELED", stage="account_deleting")
        )
        session_digest = hashlib.sha256(
            "|".join(sorted(session_hashes)).encode()
        ).hexdigest()
        integrity = hmac.new(
            _journal_key().encode(),
            (
                f"{user_hash}:{now.isoformat()}:{session_digest}:"
                f"{','.join(sorted(credential_versions))}"
            ).encode(),
            hashlib.sha256,
        ).hexdigest()
        journal = DeletionJournal(
            user_id_hash=user_hash,
            revoked_credential_versions=credential_versions,
            revoked_session_digest=session_digest,
            integrity_hmac=integrity,
        )
        session.add(journal)
        session.flush()
        job = enqueue_job(session, owner_id=auth.user_id, kind=DELETE_JOB_KIND)
        return DeleteReceipt(
            operation_id=job.id,
            state="DELETING",
            journal_hmac=integrity,
            receipt_expires_at=now + timedelta(days=30),
        )


@lru_cache(maxsize=1)
def _journal_key() -> str:
    settings = get_settings()
    return settings.app_hash_key or settings.oidc_client_secret or "local-journal-key"


@router.get("/account/deletion", response_model=DeleteReceipt)
def deletion_status(auth: AuthContext = Depends(require_auth)) -> DeleteReceipt:
    user_hash = hashlib.sha256(str(auth.user_id).encode()).hexdigest()
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        journal = session.scalar(
            select(DeletionJournal).where(DeletionJournal.user_id_hash == user_hash)
        )
        state = _current_user_state(session)
        if journal is None:
            raise HTTPException(status_code=404, detail="no deletion recorded")
        job = session.scalar(
            select(Job)
            .where(
                Job.user_id == auth.user_id,
                Job.kind == DELETE_JOB_KIND,
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return DeleteReceipt(
            operation_id=job.id if job else None,
            state=state or "DELETED",
            journal_hmac=journal.integrity_hmac,
            receipt_expires_at=journal.deleted_at + timedelta(days=30),
        )
