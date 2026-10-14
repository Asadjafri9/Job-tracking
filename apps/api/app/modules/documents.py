"""Owner-scoped document upload, private download, and lifecycle APIs (DOC-001)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Engine

from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.idempotency import (
    IdempotencyConflict,
    claim_idempotency,
    fingerprint,
    release_quota,
    reserve_quota,
)
from app.db.jobs import enqueue_job
from app.db.models import Document, ProfileFactVersion
from app.db.tenant import tenant_session
from app.storage.blob import DocumentStorage, StorageError, document_storage

router = APIRouter(prefix="/api/v1", tags=["documents"])

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_ACCOUNT_BYTES = 50 * 1024 * 1024
MAX_ACTIVE_DOCUMENTS = 10
PARSE_JOB_KIND = "document.parse"
BLOB_CLEANUP_JOB_KIND = "document.blob_cleanup"

PDF_MEDIA = "application/pdf"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DocumentType = Literal["RESUME", "LINKEDIN_PDF", "COVER_LETTER", "SUPPORTING_DOCUMENT", "OTHER"]
TYPE_MEDIA: dict[str, set[str]] = {
    "RESUME": {PDF_MEDIA, DOCX_MEDIA},
    "LINKEDIN_PDF": {PDF_MEDIA},
    "COVER_LETTER": {PDF_MEDIA, DOCX_MEDIA},
    "SUPPORTING_DOCUMENT": {PDF_MEDIA, DOCX_MEDIA},
    "OTHER": {PDF_MEDIA, DOCX_MEDIA},
}


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    settings = get_settings()
    return create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)


def _storage() -> DocumentStorage:
    return document_storage()


class DocumentSummary(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str
    original_state: str
    parse_state: str
    is_default: bool
    revision: int
    created_at: datetime


class DocumentList(BaseModel):
    documents: list[DocumentSummary]


class DocumentUploadResponse(DocumentSummary):
    pass


class DefaultWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_default: bool = Field(default=True)


def _summary(row: Document) -> DocumentSummary:
    return DocumentSummary(
        id=row.id,
        document_type=row.document_type,
        file_name=row.file_name,
        media_type=row.media_type,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        original_state=row.original_state,
        parse_state=row.parse_state,
        is_default=row.is_default,
        revision=row.revision,
        created_at=row.created_at,
    )


def _signature_ok(media_type: str, data: bytes) -> bool:
    if media_type == PDF_MEDIA:
        return data.startswith(b"%PDF-")
    return data.startswith(b"PK\x03\x04")


@router.get("/documents", response_model=DocumentList)
def list_documents(auth: AuthContext = Depends(require_auth)) -> DocumentList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        rows = session.scalars(
            select(Document)
            .where(Document.user_id == auth.user_id, Document.original_state != "DELETED")
            .order_by(Document.created_at.desc())
        ).all()
        return DocumentList(documents=[_summary(row) for row in rows])


@router.post("/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile,
    document_type: Annotated[DocumentType, Form()],
    auth: AuthContext = Depends(require_auth),
) -> DocumentUploadResponse:
    require_csrf(request, auth)
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="uploaded file is empty")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="document exceeds the 5 MiB limit")
    media_type = (file.content_type or "").lower()
    if media_type not in TYPE_MEDIA[document_type]:
        raise HTTPException(status_code=422, detail="unsupported document media type")
    if not _signature_ok(media_type, data):
        raise HTTPException(status_code=422, detail="file content does not match its type")
    file_name = (file.filename or "document").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    if not file_name:
        file_name = "document"
    digest = hashlib.sha256(data).hexdigest()
    idem_header = request.headers.get("Idempotency-Key")
    idempotency_key = UUID(idem_header) if idem_header else None
    input_hmac = fingerprint(
        b"document-upload",
        {"name": file_name, "size": len(data), "sha256": digest, "type": document_type},
    )
    storage = _storage()
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        if idempotency_key is not None:
            try:
                claim = claim_idempotency(
                    session,
                    owner_id=auth.user_id,
                    route_key="documents.upload",
                    key=idempotency_key,
                    input_fingerprint=input_hmac,
                    response_status=201,
                    entity_type="document",
                )
            except IdempotencyConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            if not claim.created:
                original = session.get(Document, claim.record.entity_id)
                if original is not None and original.original_state != "DELETED":
                    return DocumentUploadResponse(**_summary(original).model_dump())
        committed_bytes = int(
            session.scalar(
                select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
                    Document.user_id == auth.user_id,
                    Document.original_state.in_(["RESERVED", "READY"]),
                )
            )
            or 0
        )
        active_count = int(
            session.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.user_id == auth.user_id, Document.original_state != "DELETED")
            )
            or 0
        )
        if active_count >= MAX_ACTIVE_DOCUMENTS:
            raise HTTPException(status_code=409, detail="document count limit reached")
        row = Document(
            user_id=auth.user_id,
            document_type=document_type,
            storage_key="pending",
            file_name=file_name,
            media_type=media_type,
            size_bytes=len(data),
            sha256=digest,
            original_state="RESERVED",
            parse_state="NOT_STARTED",
        )
        session.add(row)
        session.flush()
        try:
            reserve_quota(
                session,
                owner_id=auth.user_id,
                kind="document_bytes",
                reservation_key=row.id,
                amount=len(data),
                committed_usage=committed_bytes,
                maximum=MAX_ACCOUNT_BYTES,
            )
        except IdempotencyConflict as error:
            raise HTTPException(status_code=409, detail="storage quota exceeded") from error
        row.storage_key = f"{auth.user_id}/{row.id}/v{row.revision}/{digest[:16]}"
        try:
            storage.put(row.storage_key, data, media_type)
        except StorageError as error:
            raise HTTPException(status_code=503, detail="document storage failed") from error
        row.original_state = "READY"
        row.parse_state = "QUEUED"
        enqueue_job(
            session,
            owner_id=auth.user_id,
            kind=PARSE_JOB_KIND,
            reference_type="document",
            reference_id=row.id,
        )
        # The reservation only guards the upload window; once READY the bytes
        # are committed usage, so release it to avoid double counting.
        release_quota(
            session,
            owner_id=auth.user_id,
            kind="document_bytes",
            reservation_key=row.id,
        )
        session.flush()
        return DocumentUploadResponse(**_summary(row).model_dump())


@router.get("/documents/{document_id}", response_model=DocumentSummary)
def get_document(document_id: UUID, auth: AuthContext = Depends(require_auth)) -> DocumentSummary:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(Document).where(
                Document.user_id == auth.user_id,
                Document.id == document_id,
                Document.original_state != "DELETED",
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return _summary(row)


@router.get("/documents/{document_id}/download")
def download_document(document_id: UUID, auth: AuthContext = Depends(require_auth)) -> Response:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(Document).where(
                Document.user_id == auth.user_id,
                Document.id == document_id,
                Document.original_state == "READY",
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        storage_key = row.storage_key
        media_type = row.media_type
        file_name = row.file_name
    try:
        data = _storage().get(storage_key)
    except StorageError as error:
        raise HTTPException(status_code=503, detail="document download failed") from error
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/documents/{document_id}/default", response_model=DocumentSummary)
def set_default_document(
    document_id: UUID,
    body: DefaultWrite,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> DocumentSummary:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(Document)
            .where(
                Document.user_id == auth.user_id,
                Document.id == document_id,
                Document.original_state == "READY",
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if body.is_default:
            session.execute(
                update(Document)
                .where(Document.user_id == auth.user_id, Document.is_default.is_(True))
                .values(is_default=False)
            )
        # Revision tracks document content; flag/lifecycle changes keep it
        # stable so anchored extractions and fact versions stay valid.
        row.is_default = body.is_default
        session.flush()
        return _summary(row)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> Response:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(Document)
            .where(
                Document.user_id == auth.user_id,
                Document.id == document_id,
                Document.original_state != "DELETED",
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        row.original_state = "DELETED"
        row.is_current = False
        row.is_default = False
        row.deleted_at = datetime.now(UTC)
        # Revision tracks content and stays stable so sourced fact versions
        # keep their (document, revision) anchor after deletion.
        # Replacing or deleting a source marks sourced facts for review.
        session.execute(
            update(ProfileFactVersion)
            .where(
                ProfileFactVersion.user_id == auth.user_id,
                ProfileFactVersion.document_id == row.id,
                ProfileFactVersion.confirmation_state == "CONFIRMED",
            )
            .values(confirmation_state="REVIEW_REQUIRED", confirmed_at=None)
        )
        release_quota(
            session,
            owner_id=auth.user_id,
            kind="document_bytes",
            reservation_key=row.id,
        )
        # The blob delete is a durable retry job: a transient storage failure
        # can never leave the private blob retained after reported deletion.
        enqueue_job(
            session,
            owner_id=auth.user_id,
            kind=BLOB_CLEANUP_JOB_KIND,
            reference_type="document",
            reference_id=row.id,
        )
        session.flush()
    return Response(status_code=204)
