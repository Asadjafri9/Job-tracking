"""Email application drafts and honest send tracking (M4).

Drafts are versioned and owner-scoped; generation runs through the
consent-gated provider router with confirmed EMAIL-permitted facts only.
Opening Gmail compose is recorded as an event, never as Applied — only an
explicit user confirmation with a sent date creates/updates the EMAIL
application with an immutable snapshot.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ai.router import RoutingError, run_operation
from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import (
    Application,
    ApplicationStatusEvent,
    Document,
    EmailDraft,
    EmailDraftDocument,
    EmailDraftEvent,
)
from app.db.tenant import tenant_session
from app.modules.credentials import _key_encryption_provider
from app.modules.profile import confirmed_facts_for_purpose

router = APIRouter(prefix="/api/v1", tags=["email"])

MAX_DRAFTS = 200
MAX_SUBJECT = 200
MAX_BODY = 10_000
EMAIL_RE = re.compile(r"^[^@\s\r\n]+@[^@\s\r\n]+\.[^@\s\r\n]+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _clean_header(value: str, field: str) -> str:
    if "\r" in value or "\n" in value:
        raise HTTPException(status_code=422, detail=f"{field} cannot contain line breaks")
    return value.strip()


def _valid_recipient(value: str) -> str:
    cleaned = _clean_header(value, "recipient_email")
    if not EMAIL_RE.fullmatch(cleaned):
        raise HTTPException(status_code=422, detail="recipient_email is not a valid address")
    return cleaned


class EmailDraftCreate(StrictModel):
    recipient_email: str = Field(min_length=3, max_length=320)
    employer: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    job_description: str | None = Field(default=None, max_length=20_000)
    start_message: str | None = Field(default=None, max_length=2_000)
    style_document_ids: list[UUID] = Field(default_factory=list, max_length=3)


class EmailDraftPatch(StrictModel):
    subject: str | None = Field(default=None, max_length=MAX_SUBJECT)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    state: Literal["CANCELED"] | None = None


class GenerateRequest(StrictModel):
    expected_revision: int = Field(ge=1)


class EventRequest(StrictModel):
    event_idempotency_key: UUID


class ConfirmSentRequest(EventRequest):
    sent_date: date
    note: str | None = Field(default=None, max_length=2_000)


class EmailDraftView(StrictModel):
    id: UUID
    recipient_email: str
    employer: str
    role: str
    subject: str
    body: str
    state: str
    revision: int
    application_id: UUID | None
    created_at: datetime
    updated_at: datetime


class EmailDraftList(StrictModel):
    drafts: list[EmailDraftView]


class GenerateView(StrictModel):
    revision: int
    subject: str
    body: str
    provider: str | None
    model: str | None
    replayed: bool


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


def _get_draft(session: Session, owner_id: UUID, draft_id: UUID) -> EmailDraft:
    row = session.scalar(
        select(EmailDraft)
        .where(EmailDraft.user_id == owner_id, EmailDraft.id == draft_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Email draft not found")
    return row


def _email_application(session: Session, owner_id: UUID, draft: EmailDraft) -> Application | None:
    for row in session.scalars(
        select(Application).where(
            Application.user_id == owner_id,
            Application.channel == "EMAIL",
        )
    ):
        snapshot = row.context_snapshot or {}
        if snapshot.get("email_draft_id") == str(draft.id):
            return row
    return None


def _view(session: Session, row: EmailDraft) -> EmailDraftView:
    application = _email_application(session, row.user_id, row)
    return EmailDraftView(
        id=row.id,
        recipient_email=row.recipient_email,
        employer=row.employer,
        role=row.role,
        subject=row.subject,
        body=row.body,
        state=row.state,
        revision=row.revision,
        application_id=application.id if application else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _fact_snapshot(
    session: Session, owner_id: UUID
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    facts = confirmed_facts_for_purpose(session, owner_id, "EMAIL")
    payloads, refs = [], []
    for fact in facts:
        latest = max(fact.versions, key=lambda version: version.revision)
        payloads.append(
            {
                "fact_key": fact.fact_key,
                "value_type": fact.value_type,
                "value": fact.value if isinstance(fact.value, str) else str(fact.value),
            }
        )
        refs.append(
            {
                "fact_id": str(fact.id),
                "fact_key": fact.fact_key,
                "version_id": str(latest.id),
                "revision": latest.revision,
            }
        )
    return payloads, refs


@router.post("/email-drafts", response_model=EmailDraftView, status_code=201)
def create_draft(
    body: EmailDraftCreate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> EmailDraftView:
    require_csrf(request, auth)
    recipient = _valid_recipient(body.recipient_email)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        count = int(
            session.scalar(
                select(func.count())
                .select_from(EmailDraft)
                .where(
                    EmailDraft.user_id == auth.user_id,
                    EmailDraft.state != "CANCELED",
                )
            )
            or 0
        )
        if count >= MAX_DRAFTS:
            raise HTTPException(status_code=409, detail="email draft limit reached")
        for document_id in body.style_document_ids:
            document = session.scalar(
                select(Document).where(
                    Document.user_id == auth.user_id,
                    Document.id == document_id,
                    Document.original_state == "READY",
                )
            )
            if document is None:
                raise HTTPException(
                    status_code=409, detail=f"document {document_id} is not available"
                )
        _, refs = _fact_snapshot(session, auth.user_id)
        row = EmailDraft(
            user_id=auth.user_id,
            recipient_email=recipient,
            employer=_clean_header(body.employer, "employer"),
            role=_clean_header(body.role, "role"),
            job_description=body.job_description,
            subject="",
            body="",
            source_fact_versions=refs,
        )
        session.add(row)
        session.flush()
        for position, document_id in enumerate(body.style_document_ids, start=1):
            document = session.scalar(
                select(Document).where(
                    Document.user_id == auth.user_id, Document.id == document_id
                )
            )
            if document is None:
                raise HTTPException(
                    status_code=422, detail="style document not found"
                )
            session.add(
                EmailDraftDocument(
                    user_id=auth.user_id,
                    email_draft_id=row.id,
                    document_id=document_id,
                    document_revision=document.revision,
                    position=position,
                )
            )
        session.flush()
        view = _view(session, row)
        view.state = "DRAFT"
        return view


@router.get("/email-drafts", response_model=EmailDraftList)
def list_drafts(auth: AuthContext = Depends(require_auth)) -> EmailDraftList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        rows = session.scalars(
            select(EmailDraft)
            .where(EmailDraft.user_id == auth.user_id)
            .order_by(EmailDraft.updated_at.desc())
            .limit(MAX_DRAFTS)
        ).all()
        return EmailDraftList(drafts=[_view(session, row) for row in rows])


@router.get("/email-drafts/{draft_id}", response_model=EmailDraftView)
def get_draft(draft_id: UUID, auth: AuthContext = Depends(require_auth)) -> EmailDraftView:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        return _view(session, _get_draft(session, auth.user_id, draft_id))


@router.post("/email-drafts/{draft_id}/generate", response_model=GenerateView)
def generate_draft(
    draft_id: UUID,
    body: GenerateRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> GenerateView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_draft(session, auth.user_id, draft_id)
        if row.state == "CANCELED":
            raise HTTPException(status_code=409, detail="draft was canceled")
        if row.revision != body.expected_revision:
            raise HTTPException(status_code=409, detail="draft revision conflict")
        payloads, refs = _fact_snapshot(session, auth.user_id)
        try:
            result = run_operation(
                session,
                owner_id=auth.user_id,
                kind="EMAIL",
                request_payload={
                    "recipient_email": row.recipient_email,
                    "employer": row.employer,
                    "role": row.role,
                    "job_excerpt": (row.job_description or "")[:10_000],
                    "facts": payloads,
                    "tone_tips": [],
                },
                purpose="INTERACTIVE",
                idempotency_key=uuid5(
                    NAMESPACE_URL, f"email-draft:{row.id}:{row.revision + 1}"
                ),
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
                detail="provider outcome is uncertain; your edits are preserved",
            )
        if result.state != "SUCCEEDED" or result.content is None:
            raise HTTPException(status_code=503, detail="generation could not be completed")
        subject = _clean_header(str(result.content.get("subject", "")), "subject")[
            :MAX_SUBJECT
        ]
        generated_body = str(result.content.get("body", ""))[:MAX_BODY]
        if not subject or not generated_body.strip():
            raise HTTPException(
                status_code=503, detail="provider returned an incomplete draft"
            )
        row.subject = subject
        row.body = generated_body
        row.source_fact_versions = refs
        row.revision += 1
        row.state = "READY_FOR_REVIEW"
        session.flush()
        return GenerateView(
            revision=row.revision,
            subject=row.subject,
            body=row.body,
            provider=result.provider,
            model=result.model,
            replayed=result.replayed,
        )


@router.patch("/email-drafts/{draft_id}", response_model=EmailDraftView)
def patch_draft(
    draft_id: UUID,
    body: EmailDraftPatch,
    request: Request,
    if_match: str | None = Header(default=None),
    auth: AuthContext = Depends(require_auth),
) -> EmailDraftView:
    require_csrf(request, auth)
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match revision is required")
    try:
        expected = int(if_match.strip('"'))
    except ValueError:
        raise HTTPException(status_code=422, detail="If-Match must be an integer") from None
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_draft(session, auth.user_id, draft_id)
        if row.revision != expected:
            raise HTTPException(status_code=409, detail="draft revision conflict")
        if row.state in {"USER_CONFIRMED_SENT", "CANCELED"}:
            raise HTTPException(
                status_code=409, detail=f"draft is {row.state.lower().replace('_', ' ')}"
            )
        if body.state == "CANCELED":
            row.state = "CANCELED"
            row.revision += 1
            session.flush()
            return _view(session, row)
        changed = False
        if body.subject is not None:
            row.subject = _clean_header(body.subject, "subject")[:MAX_SUBJECT]
            changed = True
        if body.body is not None:
            row.body = body.body[:MAX_BODY]
            changed = True
        if changed:
            row.revision += 1  # edits always create a new revision
            row.state = "READY_FOR_REVIEW"
        session.flush()
        return _view(session, row)


@router.post("/email-drafts/{draft_id}/compose-opened", response_model=EmailDraftView)
def compose_opened(
    draft_id: UUID,
    body: EventRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> EmailDraftView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        existing = session.scalar(
            select(EmailDraftEvent).where(
                EmailDraftEvent.user_id == auth.user_id,
                EmailDraftEvent.event_idempotency_key == body.event_idempotency_key,
            )
        )
        row = _get_draft(session, auth.user_id, draft_id)
        if existing is not None:
            if existing.email_draft_id != row.id:
                raise HTTPException(
                    status_code=409, detail="event key belongs to another draft"
                )
            return _view(session, row)  # idempotent replay
        if row.state not in {"READY_FOR_REVIEW", "COMPOSE_OPENED"}:
            raise HTTPException(
                status_code=409,
                detail="only a reviewed draft can open compose",
            )
        session.add(
            EmailDraftEvent(
                user_id=auth.user_id,
                email_draft_id=row.id,
                event_idempotency_key=body.event_idempotency_key,
                event_type="COMPOSE_OPENED",
                draft_revision=row.revision,
                occurred_at=datetime.now(UTC),
                evidence={"kind": "compose_opened"},
            )
        )
        row.state = "COMPOSE_OPENED"  # an open is never Applied or sent
        session.flush()
        return _view(session, row)


@router.post("/email-drafts/{draft_id}/confirm-sent")
def confirm_sent(
    draft_id: UUID,
    body: ConfirmSentRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_draft(session, auth.user_id, draft_id)
        prior_event = session.scalar(
            select(EmailDraftEvent).where(
                EmailDraftEvent.user_id == auth.user_id,
                EmailDraftEvent.event_idempotency_key == body.event_idempotency_key,
            )
        )
        if prior_event is not None:
            if prior_event.email_draft_id != row.id:
                raise HTTPException(
                    status_code=409, detail="event key belongs to another draft"
                )
            application = (
                session.get(Application, prior_event.application_id)
                if prior_event.application_id
                else None
            )
            return {
                "application_id": str(prior_event.application_id or ""),
                "status": application.status if application else "APPLIED",
                "replayed": True,
            }
        if row.state not in {"READY_FOR_REVIEW", "COMPOSE_OPENED", "USER_CONFIRMED_SENT"}:
            raise HTTPException(status_code=409, detail="draft cannot be confirmed")
        existing = _email_application(session, auth.user_id, row)
        if (
            existing is not None
            and (existing.context_snapshot or {}).get("draft_revision") == row.revision
        ):
            session.add(
                EmailDraftEvent(
                    user_id=auth.user_id,
                    email_draft_id=row.id,
                    application_id=existing.id,
                    event_idempotency_key=body.event_idempotency_key,
                    event_type="USER_CONFIRMED_SENT",
                    draft_revision=row.revision,
                    occurred_at=datetime.now(UTC),
                    evidence={"kind": "USER_CONFIRMED_EMAIL", "replayed": True},
                )
            )
            session.flush()
            return {
                "application_id": str(existing.id),
                "status": existing.status,
                "replayed": True,
            }
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="a different draft revision was already recorded as sent",
            )
        document_rows = session.scalars(
            select(EmailDraftDocument).where(
                EmailDraftDocument.user_id == auth.user_id,
                EmailDraftDocument.email_draft_id == row.id,
            )
        ).all()
        snapshot = {
            "email_draft_id": str(row.id),
            "draft_revision": row.revision,
            "recipient_email": row.recipient_email,
            "subject": row.subject,
            "body": row.body,
            "source_fact_versions": row.source_fact_versions,
            "confirmed_at": datetime.now(UTC).isoformat(),
        }
        evidence = {
            "kind": "USER_CONFIRMED_EMAIL",
            "draft_revision": row.revision,
            "note": body.note,
        }
        application = Application(
            user_id=auth.user_id,
            channel="EMAIL",
            email_draft_id=row.id,
            employer=row.employer,
            role=row.role,
            attempt_number=1,
            status="APPLIED",
            attempt_at=datetime.now(UTC),
            applied_at=datetime.now(UTC),
            applied_date=body.sent_date,
            context_snapshot=snapshot,
            document_metadata_snapshot=[
                {
                    "document_id": str(link.document_id),
                    "revision": link.document_revision,
                }
                for link in document_rows
            ],
        )
        session.add(application)
        session.flush()
        session.add(
            ApplicationStatusEvent(
                user_id=auth.user_id,
                application_id=application.id,
                old_status=None,
                new_status="APPLIED",
                source="USER_CONFIRMATION",
                evidence_snapshot=evidence,
            )
        )
        session.add(
            EmailDraftEvent(
                user_id=auth.user_id,
                email_draft_id=row.id,
                application_id=application.id,
                event_idempotency_key=body.event_idempotency_key,
                event_type="USER_CONFIRMED_SENT",
                draft_revision=row.revision,
                occurred_at=datetime.now(UTC),
                evidence=evidence,
            )
        )
        row.state = "USER_CONFIRMED_SENT"
        session.flush()
        return {
            "application_id": str(application.id),
            "status": application.status,
            "replayed": False,
        }
