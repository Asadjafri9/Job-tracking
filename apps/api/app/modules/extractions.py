"""Extraction preview and candidate review APIs (DOC-003).

Candidates stay private until the owner confirms or rejects each one. Confirming
writes a DOCUMENT-sourced, anchored fact version; a conflicting existing value
is replaced only through an explicit user choice, never merged silently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ai.contract import ExtractionInput, ExtractionOutput
from app.ai.router import RoutingError, run_operation
from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import LOCAL_TEST_KEK, get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import Document, DocumentExtraction, Profile, ProfileFact, ProfileFactVersion
from app.db.tenant import tenant_session
from app.security.key_encryption import KeyEncryptionProvider, LocalAesGcmKeyEncryption
from app.worker.parsing import ParseResult, split_sections

router = APIRouter(prefix="/api/v1", tags=["extractions"])

PROMPT_VERSION = "extract-profile-candidates-v1"


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    settings = get_settings()
    return create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)


def _key_encryption_provider() -> KeyEncryptionProvider:
    settings = get_settings()
    if settings.credential_kek_provider == "key_vault":
        from app.security.key_encryption import KeyVaultKeyEncryption

        if not settings.key_vault_credential_kek_id:
            raise HTTPException(status_code=503, detail="Credential key service is not configured")
        return KeyVaultKeyEncryption(settings.key_vault_credential_kek_id)
    import base64

    encoded = settings.credential_kek_base64 or LOCAL_TEST_KEK
    return LocalAesGcmKeyEncryption(base64.b64decode(encoded, validate=True), "local-test-v1")


class CandidateView(BaseModel):
    index: int
    fact_key: str
    value_type: str
    value: object
    section_id: int
    anchor: dict[str, object]
    decision: str | None


class ExtractionView(BaseModel):
    id: UUID
    document_id: UUID
    parse_version: str
    prompt_version: str | None
    model_version: str | None
    review_state: str
    extracted_text: str | None
    source_anchors: list[dict[str, object]]
    candidates: list[CandidateView]
    redacted_error: str | None


class CandidateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["CONFIRM", "REJECT"]
    fact_key: str | None = Field(default=None, max_length=128)
    value_type: Literal["TEXT", "NUMBER", "DATE", "BOOLEAN", "URL", "JSON"] | None = None
    value: object = None


def _view(row: DocumentExtraction) -> ExtractionView:
    candidates = [
        CandidateView(
            index=index,
            fact_key=str(candidate.get("fact_key", "")),
            value_type=str(candidate.get("value_type", "TEXT")),
            value=candidate.get("value"),
            section_id=int(candidate.get("section_id", 0)),
            anchor=dict(candidate.get("anchor") or {}),
            decision=candidate.get("decision"),
        )
        for index, candidate in enumerate(row.candidates)
    ]
    return ExtractionView(
        id=row.id,
        document_id=row.document_id,
        parse_version=row.parse_version,
        prompt_version=row.prompt_version,
        model_version=row.model_version,
        review_state=row.review_state,
        extracted_text=row.extracted_text,
        source_anchors=list(row.source_anchors),
        candidates=candidates,
        redacted_error=row.redacted_error,
    )


JsonScalar = dict[str, Any] | list[Any] | str | int | float | bool | None


def _load_extraction(
    session: Session, owner_id: UUID, extraction_id: UUID
) -> DocumentExtraction:
    row = cast(
        DocumentExtraction | None,
        session.scalar(
            select(DocumentExtraction).where(
                DocumentExtraction.user_id == owner_id,
                DocumentExtraction.id == extraction_id,
            )
        ),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return row


@router.get("/documents/{document_id}/extractions", response_model=list[ExtractionView])
def list_extractions(
    document_id: UUID, auth: AuthContext = Depends(require_auth)
) -> list[ExtractionView]:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        document = session.scalar(
            select(Document).where(
                Document.user_id == auth.user_id,
                Document.id == document_id,
                Document.original_state != "DELETED",
            )
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        rows = session.scalars(
            select(DocumentExtraction)
            .where(
                DocumentExtraction.user_id == auth.user_id,
                DocumentExtraction.document_id == document_id,
            )
            .order_by(DocumentExtraction.created_at.desc())
        ).all()
        return [_view(row) for row in rows]


@router.post(
    "/documents/{document_id}/extractions/{extraction_id}/extract",
    response_model=ExtractionView,
)
def run_extraction(
    document_id: UUID,
    extraction_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> ExtractionView:
    """Run the consented provider extraction over stored bounded text."""
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        extraction = _load_extraction(session, auth.user_id, extraction_id)
        if extraction.document_id != document_id or extraction.review_state != "REVIEW_REQUIRED":
            raise HTTPException(status_code=409, detail="Extraction is not awaiting review")
        if not extraction.extracted_text:
            raise HTTPException(status_code=422, detail="No extracted text to analyze")
        sections = split_sections(
            ParseResult(
                status="OK",
                text=extraction.extracted_text,
                anchors=list(extraction.source_anchors),
            )
        )
        if not sections:
            raise HTTPException(status_code=422, detail="No usable sections to analyze")
        document = session.scalar(
            select(Document).where(
                Document.user_id == auth.user_id, Document.id == document_id
            )
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        payload = ExtractionInput(
            document_type=document.document_type, sections=sections
        ).model_dump()
        try:
            result = run_operation(
                session,
                owner_id=auth.user_id,
                kind="EXTRACTION",
                request_payload=payload,
                purpose="INTERACTIVE",
                idempotency_key=uuid4(),
                key_encryption=_key_encryption_provider(),
            )
        except RoutingError as error:
            status = 403 if error.code == "consent_required" else 409
            if error.code in {"providers_unavailable", "quota_exceeded"}:
                status = 503 if error.code == "providers_unavailable" else 429
            raise HTTPException(status_code=status, detail=error.detail) from error
        if result.state == "UNKNOWN":
            raise HTTPException(
                status_code=503,
                detail="provider outcome is uncertain; nothing else was charged",
            )
        if result.state != "SUCCEEDED" or result.content is None:
            raise HTTPException(status_code=503, detail="extraction could not be completed")
        output = ExtractionOutput.model_validate(result.content)
        candidates = []
        for candidate in output.candidates:
            candidates.append(
                {
                    "fact_key": candidate.fact_key,
                    "value_type": candidate.value_type,
                    "value": candidate.value,
                    "section_id": candidate.section_id,
                    "anchor": candidate.anchor.model_dump(),
                    "decision": None,
                }
            )
        extraction.candidates = candidates[:200]
        extraction.candidate_count = len(extraction.candidates)
        extraction.prompt_version = PROMPT_VERSION
        extraction.model_version = result.model
        session.flush()
        return _view(extraction)


@router.post(
    "/extractions/{extraction_id}/candidates/{index}/decision",
    response_model=ExtractionView,
)
def decide_candidate(
    extraction_id: UUID,
    index: int,
    body: CandidateDecision,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> ExtractionView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        extraction = _load_extraction(session, auth.user_id, extraction_id)
        if extraction.review_state != "REVIEW_REQUIRED":
            raise HTTPException(status_code=409, detail="Extraction is not awaiting review")
        candidates = list(extraction.candidates)
        if index < 0 or index >= len(candidates):
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate = dict(candidates[index])
        if candidate.get("decision") is not None:
            raise HTTPException(status_code=409, detail="Candidate already decided")
        profile = session.scalar(
            select(Profile).where(Profile.user_id == auth.user_id).with_for_update()
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile is not initialized")
        if body.action == "REJECT":
            candidate["decision"] = "REJECTED"
            candidates[index] = candidate
            extraction.candidates = candidates
            session.flush()
            return _view(extraction)
        fact_key = (body.fact_key or candidate.get("fact_key") or "").strip().lower()
        value_type = body.value_type or candidate.get("value_type") or "TEXT"
        value = body.value if body.value is not None else candidate.get("value")
        if not fact_key or value is None:
            raise HTTPException(status_code=422, detail="a fact key and value are required")
        fact = session.scalar(
            select(ProfileFact)
            .where(
                ProfileFact.user_id == auth.user_id,
                ProfileFact.profile_id == profile.id,
                ProfileFact.fact_key == fact_key,
            )
            .with_for_update()
        )
        if fact is None:
            fact = ProfileFact(
                user_id=auth.user_id,
                profile_id=profile.id,
                fact_key=fact_key,
                value_type=value_type,
                value=cast(JsonScalar, value),
                sensitivity="NORMAL",
                allowed_purposes=[],
                current_revision=0,
                is_active=True,
            )
            session.add(fact)
        else:
            fact.is_active = True
        fact.value_type = value_type
        fact.value = cast(JsonScalar, value)
        fact.current_revision += 1
        session.flush()
        anchor = candidate.get("anchor") or {}
        session.add(
            ProfileFactVersion(
                user_id=auth.user_id,
                profile_fact_id=fact.id,
                revision=fact.current_revision,
                value=value,
                source_type="DOCUMENT",
                source_ref=f"document:{extraction.document_id}:candidate:{index}",
                document_id=extraction.document_id,
                document_revision=extraction.document_revision,
                page_number=anchor.get("page") if isinstance(anchor.get("page"), int) else None,
                source_anchor={
                    "extraction_id": str(extraction.id),
                    "candidate_index": index,
                    "anchor": anchor,
                },
                confirmation_state="CONFIRMED",
                confirmed_at=datetime.now(UTC),
            )
        )
        if profile.current_revision >= 2_147_483_647:
            raise HTTPException(status_code=409, detail="Profile revision limit reached")
        profile.current_revision += 1
        candidate["decision"] = "CONFIRMED"
        candidate["fact_key"] = fact_key
        candidate["value_type"] = value_type
        candidate["value"] = value
        candidate["fact_id"] = str(fact.id)
        candidates[index] = candidate
        extraction.candidates = candidates
        session.flush()
        return _view(extraction)
