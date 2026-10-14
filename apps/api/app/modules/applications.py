"""Application sessions, honest submission tracking, and dashboard (M3).

Prepared sessions never count as applications. Trusted extension evidence
creates or updates at most one application per session; a click is never
recorded as APPLIED. All state transitions append immutable history rows and
snapshots so earlier evidence is preserved.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ai.contract import FormFieldSpec
from app.ai.router import RoutingError, run_operation
from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import (
    Application,
    ApplicationAnswer,
    ApplicationSession,
    ApplicationStatusEvent,
    Document,
    Profile,
    ProfileFact,
    ProfileFactVersion,
    SubmissionEvent,
)
from app.db.tenant import tenant_session
from app.modules.credentials import _key_encryption_provider

router = APIRouter(prefix="/api/v1", tags=["applications"])

MAX_SESSIONS = 500
MAX_QUESTIONS = 10
MAX_OBSERVED_AGE = timedelta(hours=24)
MAX_OBSERVED_SKEW = timedelta(minutes=5)
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}
SESSION_OPEN_STATES = {"PREPARED", "ANALYZING", "READY_TO_REVIEW"}
SESSION_TTL = timedelta(hours=24)
APPLICATION_STATUSES = {"SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"}


def _session_is_open(row: ApplicationSession, now: datetime) -> bool:
    return row.state in SESSION_OPEN_STATES and (
        row.expires_at is None or row.expires_at > now
    )


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactVersionRef(StrictModel):
    fact_id: UUID
    revision: int = Field(ge=1)


class DocumentVersionRef(StrictModel):
    document_id: UUID
    revision: int = Field(ge=1)


class SessionCreate(StrictModel):
    employer: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    raw_job_url: str | None = Field(default=None, max_length=2048)
    job_context: dict[str, Any] = Field(default_factory=dict)
    form_reference: str | None = Field(default=None, max_length=512)
    selected_fact_versions: list[FactVersionRef] = Field(default_factory=list, max_length=100)
    selected_document_versions: list[DocumentVersionRef] = Field(
        default_factory=list, max_length=10
    )


class SessionView(StrictModel):
    id: UUID
    employer: str | None
    role: str | None
    raw_job_url: str | None
    canonical_job_url: str | None
    state: str
    profile_revision: int
    context_revision: int
    form_reference: str | None
    draft_answers: dict[str, Any] | None
    created_at: datetime
    expires_at: datetime | None


class SessionDetail(SessionView):
    job_context: dict[str, Any]
    selected_fact_versions: list[dict[str, Any]]
    selected_document_versions: list[dict[str, Any]]
    application_id: UUID | None


class SessionList(StrictModel):
    sessions: list[SessionView]


class DraftAnswersRequest(StrictModel):
    questions: list[FormFieldSpec] = Field(min_length=1, max_length=MAX_QUESTIONS)
    expected_profile_revision: int = Field(ge=1)
    context_excerpt: str = Field(default="", max_length=10_000)


class AppliedAnswerEntry(StrictModel):
    field_id: str = Field(min_length=1, max_length=128)
    value: str | list[str] | bool | None = None
    status: Literal["filled", "skipped", "filled_invalid", "unknown"]
    expected_option_ids: list[str] = Field(default_factory=list, max_length=100)


class AppliedAnswersRequest(StrictModel):
    entries: list[AppliedAnswerEntry] = Field(max_length=50)
    expected_context_revision: int = Field(ge=1)


class DraftAnswersView(StrictModel):
    revision: int
    provider: str | None
    model: str | None
    answers: list[dict[str, Any]]
    replayed: bool


class SubmissionEventCreate(StrictModel):
    event_idempotency_key: UUID
    application_session_id: UUID
    evidence_type: Literal["SUBMIT_CLICK", "VALIDATION_BLOCKED", "SITE_SIGNAL", "UNKNOWN"]
    evidence_source: Literal["USER_GESTURE", "CONTENT_OBSERVER"]
    observed_at: datetime
    gesture_ref_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    signal_code: str | None = Field(default=None, max_length=128)
    evidence: dict[str, Any] = Field(default_factory=dict)


class SubmissionEventView(StrictModel):
    id: UUID
    evidence_type: str
    evidence_source: str
    observed_at: datetime
    signal_code: str | None
    application_id: UUID | None
    replayed: bool


class ApplicationCreate(StrictModel):
    employer: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    raw_job_url: str | None = Field(default=None, max_length=2048)
    status: Literal["SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"] = (
        "SUBMISSION_ATTEMPTED"
    )
    applied_date: date | None = None
    follow_up_date: date | None = None
    context_snapshot: dict[str, Any] = Field(default_factory=dict)


class ApplicationPatch(StrictModel):
    employer: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"] | None = None
    applied_date: date | None = None
    follow_up_date: date | None = None
    note: str | None = Field(default=None, max_length=2_000)


class ConfirmAppliedRequest(StrictModel):
    applied_date: date
    note: str | None = Field(default=None, max_length=2_000)


class ApplicationView(StrictModel):
    id: UUID
    channel: str
    employer: str
    role: str
    raw_job_url: str | None
    canonical_job_url: str | None
    attempt_number: int
    status: str
    attempt_at: datetime | None
    applied_at: datetime | None
    applied_date: date | None
    follow_up_date: date | None
    revision: int
    application_session_id: UUID | None
    created_at: datetime
    updated_at: datetime


class StatusEventView(StrictModel):
    id: UUID
    old_status: str | None
    new_status: str
    source: str
    evidence_snapshot: dict[str, Any]
    occurred_at: datetime


class ApplicationDetail(ApplicationView):
    context_snapshot: dict[str, Any]
    document_metadata_snapshot: list[dict[str, Any]]
    status_events: list[StatusEventView]
    submission_events: list[SubmissionEventView]
    answers: list[dict[str, Any]]


class ApplicationList(StrictModel):
    applications: list[ApplicationView]


class DashboardView(StrictModel):
    prepared_sessions: int
    applications_by_status: dict[str, int]
    upcoming_follow_ups: list[ApplicationView]
    recent_status_events: list[StatusEventView]


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


def _canonicalize(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        raise HTTPException(status_code=422, detail="job URL is not parseable") from None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise HTTPException(status_code=422, detail="job URL must be http(s)")
    host = parts.hostname.lower()
    if parts.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=422, detail="job URLs must use https")
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in TRACKING_PARAMS
        ]
    )
    clean = (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", query, "")
    return urlunsplit(clean)


def _session_view(row: ApplicationSession) -> SessionView:
    drafts = (row.job_context or {}).get("draft_answers")
    return SessionView(
        id=row.id,
        employer=row.employer,
        role=row.role,
        raw_job_url=row.raw_job_url,
        canonical_job_url=row.canonical_job_url,
        state=row.state,
        profile_revision=row.profile_revision,
        context_revision=row.context_revision,
        form_reference=row.form_reference,
        draft_answers=drafts if isinstance(drafts, dict) else None,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def _application_view(row: Application) -> ApplicationView:
    return ApplicationView(
        id=row.id,
        channel=row.channel,
        employer=row.employer,
        role=row.role,
        raw_job_url=row.raw_job_url,
        canonical_job_url=row.canonical_job_url,
        attempt_number=row.attempt_number,
        status=row.status,
        attempt_at=row.attempt_at,
        applied_at=row.applied_at,
        applied_date=row.applied_date,
        follow_up_date=row.follow_up_date,
        revision=row.revision,
        application_session_id=row.application_session_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _status_event_view(row: ApplicationStatusEvent) -> StatusEventView:
    return StatusEventView(
        id=row.id,
        old_status=row.old_status,
        new_status=row.new_status,
        source=row.source,
        evidence_snapshot=row.evidence_snapshot or {},
        occurred_at=row.occurred_at,
    )


def _get_session(session: Session, owner_id: UUID, session_id: UUID) -> ApplicationSession:
    row = session.scalar(
        select(ApplicationSession)
        .where(
            ApplicationSession.user_id == owner_id,
            ApplicationSession.id == session_id,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application session not found")
    return row


def _snapshot_facts(
    session: Session, owner_id: UUID, refs: list[FactVersionRef]
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for ref in refs:
        fact = session.scalar(
            select(ProfileFact).where(
                ProfileFact.user_id == owner_id,
                ProfileFact.id == ref.fact_id,
                ProfileFact.is_active.is_(True),
            )
        )
        if fact is None or fact.current_revision != ref.revision:
            raise HTTPException(
                status_code=409, detail=f"fact {ref.fact_id} is missing or stale"
            )
        version = session.scalar(
            select(ProfileFactVersion)
            .where(
                ProfileFactVersion.user_id == owner_id,
                ProfileFactVersion.profile_fact_id == fact.id,
                ProfileFactVersion.revision == ref.revision,
                ProfileFactVersion.confirmation_state == "CONFIRMED",
            )
        )
        if version is None:
            raise HTTPException(
                status_code=409, detail=f"fact {ref.fact_id} has no confirmed version"
            )
        snapshots.append(
            {
                "fact_id": str(fact.id),
                "fact_key": fact.fact_key,
                "version_id": str(version.id),
                "revision": ref.revision,
                "value": fact.value,
                "sensitivity": fact.sensitivity,
                "allowed_purposes": fact.allowed_purposes,
            }
        )
    return snapshots


def _snapshot_documents(
    session: Session, owner_id: UUID, refs: list[DocumentVersionRef]
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for ref in refs:
        document = session.scalar(
            select(Document).where(
                Document.user_id == owner_id,
                Document.id == ref.document_id,
                Document.original_state == "READY",
            )
        )
        if document is None or document.revision != ref.revision:
            raise HTTPException(
                status_code=409, detail=f"document {ref.document_id} is missing or stale"
            )
        snapshots.append(
            {
                "document_id": str(document.id),
                "revision": ref.revision,
                "document_type": document.document_type,
                "file_name": document.file_name,
                "sha256": document.sha256,
            }
        )
    return snapshots


@router.post("/application-sessions", response_model=SessionDetail, status_code=201)
def create_session(
    body: SessionCreate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SessionDetail:
    require_csrf(request, auth)
    canonical = _canonicalize(body.raw_job_url)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        profile = session.scalar(
            select(Profile).where(Profile.user_id == auth.user_id).with_for_update()
        )
        if profile is None:
            raise HTTPException(status_code=409, detail="profile is not initialized")
        now = datetime.now(UTC)
        count = int(
            session.scalar(
                select(func.count())
                .select_from(ApplicationSession)
                .where(
                    ApplicationSession.user_id == auth.user_id,
                    ApplicationSession.state.in_(SESSION_OPEN_STATES),
                    or_(
                        ApplicationSession.expires_at.is_(None),
                        ApplicationSession.expires_at > now,
                    ),
                )
            )
            or 0
        )
        if count >= MAX_SESSIONS:
            raise HTTPException(status_code=409, detail="open session limit reached")
        fact_snapshots = _snapshot_facts(session, auth.user_id, body.selected_fact_versions)
        document_snapshots = _snapshot_documents(
            session, auth.user_id, body.selected_document_versions
        )
        row = ApplicationSession(
            user_id=auth.user_id,
            employer=body.employer,
            role=body.role,
            raw_job_url=body.raw_job_url,
            canonical_job_url=canonical,
            job_context=body.job_context,
            selected_fact_versions=fact_snapshots,
            selected_document_versions=document_snapshots,
            form_reference=body.form_reference,
            profile_revision=profile.current_revision,
            context_revision=1,
            expires_at=now + SESSION_TTL,
        )
        session.add(row)
        session.flush()
        return SessionDetail(
            **_session_view(row).model_dump(),
            job_context=row.job_context,
            selected_fact_versions=row.selected_fact_versions,
            selected_document_versions=row.selected_document_versions,
            application_id=None,
        )


@router.get("/application-sessions", response_model=SessionList)
def list_sessions(
    state: str | None = None,
    auth: AuthContext = Depends(require_auth),
) -> SessionList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        statement = (
            select(ApplicationSession)
            .where(ApplicationSession.user_id == auth.user_id)
            .order_by(ApplicationSession.created_at.desc())
            .limit(200)
        )
        if state is not None:
            statement = statement.where(ApplicationSession.state == state)
        return SessionList(
            sessions=[_session_view(row) for row in session.scalars(statement).all()]
        )


@router.get("/application-sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(
    session_id: UUID, auth: AuthContext = Depends(require_auth)
) -> SessionDetail:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_session(session, auth.user_id, session_id)
        application_id = session.scalar(
            select(Application.id).where(
                Application.user_id == auth.user_id,
                Application.application_session_id == row.id,
            )
        )
        return SessionDetail(
            **_session_view(row).model_dump(),
            job_context=row.job_context,
            selected_fact_versions=row.selected_fact_versions,
            selected_document_versions=row.selected_document_versions,
            application_id=application_id,
        )


@router.post("/application-sessions/{session_id}/abandon", response_model=SessionView)
def abandon_session(
    session_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SessionView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_session(session, auth.user_id, session_id)
        if row.state == "SUBMISSION_ATTEMPTED":
            raise HTTPException(
                status_code=409, detail="a submitted attempt cannot be abandoned"
            )
        row.state = "ABANDONED"
        session.flush()
        return _session_view(row)


@router.post("/application-sessions/{session_id}/draft-answers", response_model=DraftAnswersView)
def draft_answers(
    session_id: UUID,
    body: DraftAnswersRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> DraftAnswersView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_session(session, auth.user_id, session_id)
        if not _session_is_open(row, datetime.now(UTC)):
            raise HTTPException(status_code=409, detail="session is no longer open")
        profile = session.scalar(
            select(Profile).where(Profile.user_id == auth.user_id).with_for_update()
        )
        if profile is None or profile.current_revision != body.expected_profile_revision:
            raise HTTPException(
                status_code=409, detail="profile changed; re-analyze before drafting"
            )
        if profile.current_revision != row.profile_revision:
            raise HTTPException(
                status_code=409, detail="session profile snapshot is stale"
            )
        facts = [
            {
                "fact_key": snap["fact_key"],
                "value_type": "TEXT",
                "value": snap["value"] if isinstance(snap["value"], str) else str(snap["value"]),
            }
            for snap in row.selected_fact_versions
            if "AUTOFILL" in (snap.get("allowed_purposes") or ["AUTOFILL"])
        ]
        next_revision = row.context_revision + 1
        try:
            result = run_operation(
                session,
                owner_id=auth.user_id,
                kind="AUTOFILL",
                request_payload={
                    "questions": [question.model_dump() for question in body.questions],
                    "facts": facts[:50],
                    "context_excerpt": body.context_excerpt or row.job_context.get("excerpt", ""),
                },
                purpose="INTERACTIVE",
                idempotency_key=uuid5(
                    NAMESPACE_URL, f"draft:{row.id}:{next_revision}"
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
                detail="provider outcome is uncertain; nothing else was charged",
            )
        if result.state != "SUCCEEDED" or result.content is None:
            raise HTTPException(status_code=503, detail="drafting could not be completed")
        answers = result.content.get("answers", [])
        context = dict(row.job_context)
        context["draft_answers"] = {
            "revision": next_revision,
            "provider": result.provider,
            "model": result.model,
            "answers": answers,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        row.job_context = context
        row.context_revision = next_revision
        row.state = "READY_TO_REVIEW"
        session.flush()
        return DraftAnswersView(
            revision=next_revision,
            provider=result.provider,
            model=result.model,
            answers=answers,
            replayed=result.replayed,
        )


@router.post(
    "/application-sessions/{session_id}/applied-answers", response_model=SessionView
)
def record_applied_answers(
    session_id: UUID,
    body: AppliedAnswersRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SessionView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_session(session, auth.user_id, session_id)
        if not _session_is_open(row, datetime.now(UTC)):
            raise HTTPException(status_code=409, detail="session is no longer open")
        if row.context_revision != body.expected_context_revision:
            raise HTTPException(
                status_code=409, detail="session context changed; re-inspect the page"
            )
        drafts = (row.job_context or {}).get("draft_answers") or {}
        draft_by_field = {
            answer.get("field_id"): answer
            for answer in drafts.get("answers", [])
            if isinstance(answer, dict)
        }
        context = dict(row.job_context)
        context["applied_answers"] = {
            "revision": row.context_revision,
            "reported_at": datetime.now(UTC).isoformat(),
            "entries": [
                {
                    "field_id": entry.field_id,
                    "value": entry.value,
                    "status": entry.status,
                    "expected_option_ids": entry.expected_option_ids,
                    "used_fact_keys": (
                        draft_by_field.get(entry.field_id, {}).get("used_fact_keys") or []
                    ),
                }
                for entry in body.entries
            ],
        }
        row.job_context = context
        session.flush()
        return _session_view(row)


def _next_attempt_number(session: Session, owner_id: UUID, canonical: str | None) -> int:
    if canonical is None:
        return 1
    return (
        int(
            session.scalar(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.user_id == owner_id,
                    Application.canonical_job_url == canonical,
                )
            )
            or 0
        )
        + 1
    )


def _record_status(
    session: Session,
    owner_id: UUID,
    application: Application,
    new_status: str,
    source: str,
    evidence: dict[str, Any],
) -> None:
    old_status = application.status
    application.status = new_status
    if new_status == "APPLIED" and application.applied_at is None:
        application.applied_at = datetime.now(UTC)
    session.add(
        ApplicationStatusEvent(
            user_id=owner_id,
            application_id=application.id,
            old_status=old_status,
            new_status=new_status,
            source=source,
            evidence_snapshot=evidence,
        )
    )


def _application_for_session(
    session: Session, owner_id: UUID, app_session: ApplicationSession
) -> Application | None:
    return session.scalar(
        select(Application).where(
            Application.user_id == owner_id,
            Application.application_session_id == app_session.id,
        )
    )


def _create_application_from_session(
    session: Session,
    owner_id: UUID,
    app_session: ApplicationSession,
    observed_at: datetime,
) -> Application:
    application = Application(
        user_id=owner_id,
        channel="WEB_FORM",
        employer=app_session.employer or "Unknown employer",
        role=app_session.role or "Unknown role",
        raw_job_url=app_session.raw_job_url,
        canonical_job_url=app_session.canonical_job_url,
        attempt_number=_next_attempt_number(session, owner_id, app_session.canonical_job_url),
        status="SUBMISSION_ATTEMPTED",
        attempt_at=observed_at,
        application_session_id=app_session.id,
        context_snapshot={
            "job_context": app_session.job_context,
            "selected_fact_versions": app_session.selected_fact_versions,
            "profile_revision": app_session.profile_revision,
            "context_revision": app_session.context_revision,
        },
        document_metadata_snapshot=app_session.selected_document_versions,
    )
    session.add(application)
    session.flush()
    context = app_session.job_context or {}
    drafts = context.get("draft_answers") or {}
    applied = context.get("applied_answers") or {}
    provenance = {
        "provider": drafts.get("provider"),
        "model": drafts.get("model"),
        "draft_revision": drafts.get("revision"),
    }
    if applied.get("entries"):
        # User-reviewed fill results win over raw drafts.
        for entry in applied["entries"]:
            if not isinstance(entry, dict):
                continue
            session.add(
                ApplicationAnswer(
                    user_id=owner_id,
                    application_id=application.id,
                    field_key=str(entry.get("field_id", "unknown"))[:255],
                    answer_value={
                        "value": entry.get("value"),
                        "status": entry.get("status"),
                        "expected_option_ids": entry.get("expected_option_ids") or [],
                    },
                    provenance_snapshot={
                        "used_fact_keys": entry.get("used_fact_keys") or [],
                        "applied_revision": applied.get("revision"),
                        **provenance,
                    },
                )
            )
    else:
        for answer in drafts.get("answers", []):
            if not isinstance(answer, dict):
                continue
            session.add(
                ApplicationAnswer(
                    user_id=owner_id,
                    application_id=application.id,
                    field_key=str(answer.get("field_id", "unknown"))[:255],
                    answer_value={
                        "answer": answer.get("answer"),
                        "option_ids": answer.get("option_ids") or [],
                        "missing_fact": answer.get("missing_fact"),
                    },
                    provenance_snapshot={
                        "used_fact_keys": answer.get("used_fact_keys") or [],
                        **provenance,
                    },
                )
            )
    _record_status(
        session,
        owner_id,
        application,
        "SUBMISSION_ATTEMPTED",
        "SITE_EVIDENCE",
        {"kind": "trusted_submit_intent", "session_id": str(app_session.id)},
    )
    app_session.state = "SUBMISSION_ATTEMPTED"
    return application


@router.post("/submission-events", response_model=SubmissionEventView, status_code=201)
def record_submission_event(
    body: SubmissionEventCreate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SubmissionEventView:
    require_csrf(request, auth)
    now = datetime.now(UTC)
    observed = body.observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    if observed > now + MAX_OBSERVED_SKEW or observed < now - MAX_OBSERVED_AGE:
        raise HTTPException(
            status_code=422, detail="observation time is outside the accepted window"
        )
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        existing = session.scalar(
            select(SubmissionEvent).where(
                SubmissionEvent.user_id == auth.user_id,
                SubmissionEvent.event_idempotency_key == body.event_idempotency_key,
            )
        )
        if existing is not None:
            return SubmissionEventView(
                id=existing.id,
                evidence_type=existing.evidence_type,
                evidence_source=existing.evidence_source,
                observed_at=existing.observed_at,
                signal_code=existing.signal_code,
                application_id=existing.application_id,
                replayed=True,
            )
        app_session = _get_session(session, auth.user_id, body.application_session_id)
        if app_session.state == "ABANDONED":
            raise HTTPException(status_code=409, detail="session was abandoned")
        if not _session_is_open(app_session, now) and app_session.state != "SUBMISSION_ATTEMPTED":
            raise HTTPException(status_code=409, detail="session has expired")
        event = SubmissionEvent(
            user_id=auth.user_id,
            application_session_id=app_session.id,
            event_idempotency_key=body.event_idempotency_key,
            evidence_type=body.evidence_type,
            evidence_source=body.evidence_source,
            observed_at=observed,
            gesture_ref_hash=body.gesture_ref_hash,
            signal_code=body.signal_code,
            evidence=body.evidence,
        )
        session.add(event)
        application = _application_for_session(session, auth.user_id, app_session)
        if body.evidence_type in {"SUBMIT_CLICK", "UNKNOWN"}:
            if application is None:
                application = _create_application_from_session(
                    session, auth.user_id, app_session, observed
                )
            event.application_id = application.id
        elif application is not None:
            # Validation-blocked and site-signal evidence stays attached; the
            # status never advances on these signals alone.
            event.application_id = application.id
        session.flush()
        return SubmissionEventView(
            id=event.id,
            evidence_type=event.evidence_type,
            evidence_source=event.evidence_source,
            observed_at=event.observed_at,
            signal_code=event.signal_code,
            application_id=event.application_id,
            replayed=False,
        )


def _get_application(session: Session, owner_id: UUID, application_id: UUID) -> Application:
    row = session.scalar(
        select(Application)
        .where(Application.user_id == owner_id, Application.id == application_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


def _check_revision(row: Application, expected: int | None, if_match: str | None) -> int:
    supplied = expected
    if if_match is not None:
        try:
            supplied = int(if_match.strip('"'))
        except ValueError:
            raise HTTPException(status_code=422, detail="If-Match must be an integer") from None
    if supplied is None:
        raise HTTPException(status_code=428, detail="expected_revision or If-Match is required")
    if supplied != row.revision:
        raise HTTPException(status_code=409, detail="application revision conflict")
    return supplied


@router.post("/applications", response_model=ApplicationView, status_code=201)
def create_application(
    body: ApplicationCreate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> ApplicationView:
    require_csrf(request, auth)
    canonical = _canonicalize(body.raw_job_url)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = Application(
            user_id=auth.user_id,
            channel="MANUAL",
            employer=body.employer,
            role=body.role,
            raw_job_url=body.raw_job_url,
            canonical_job_url=canonical,
            attempt_number=_next_attempt_number(session, auth.user_id, canonical),
            status="SUBMISSION_ATTEMPTED",
            attempt_at=datetime.now(UTC),
            context_snapshot=body.context_snapshot,
            document_metadata_snapshot=[],
        )
        session.add(row)
        session.flush()
        initial = body.status
        evidence = {"kind": "manual_entry"}
        _record_status(session, auth.user_id, row, initial, "USER_CONFIRMATION", evidence)
        if initial == "APPLIED":
            if body.applied_date is None:
                raise HTTPException(
                    status_code=422, detail="applied_date is required for APPLIED"
                )
            row.applied_date = body.applied_date
        row.follow_up_date = body.follow_up_date
        session.flush()
        return _application_view(row)


@router.get("/applications", response_model=ApplicationList)
def list_applications(
    status: str | None = None,
    q: str | None = None,
    follow_up_before: date | None = None,
    auth: AuthContext = Depends(require_auth),
) -> ApplicationList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        statement = (
            select(Application)
            .where(Application.user_id == auth.user_id)
            .order_by(Application.updated_at.desc())
            .limit(200)
        )
        if status is not None:
            if status not in APPLICATION_STATUSES:
                raise HTTPException(status_code=422, detail="unknown status filter")
            statement = statement.where(Application.status == status)
        if q:
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(Application.employer.ilike(pattern), Application.role.ilike(pattern))
            )
        if follow_up_before is not None:
            statement = statement.where(Application.follow_up_date <= follow_up_before)
        return ApplicationList(
            applications=[_application_view(row) for row in session.scalars(statement).all()]
        )


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: UUID, auth: AuthContext = Depends(require_auth)
) -> ApplicationDetail:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_application(session, auth.user_id, application_id)
        status_events = session.scalars(
            select(ApplicationStatusEvent)
            .where(
                ApplicationStatusEvent.user_id == auth.user_id,
                ApplicationStatusEvent.application_id == row.id,
            )
            .order_by(ApplicationStatusEvent.occurred_at, ApplicationStatusEvent.id)
        ).all()
        submission_events = session.scalars(
            select(SubmissionEvent)
            .where(
                SubmissionEvent.user_id == auth.user_id,
                SubmissionEvent.application_id == row.id,
            )
            .order_by(SubmissionEvent.observed_at, SubmissionEvent.id)
        ).all()
        answers = session.scalars(
            select(ApplicationAnswer)
            .where(
                ApplicationAnswer.user_id == auth.user_id,
                ApplicationAnswer.application_id == row.id,
            )
            .order_by(ApplicationAnswer.field_key)
        ).all()
        return ApplicationDetail(
            **_application_view(row).model_dump(),
            context_snapshot=row.context_snapshot,
            document_metadata_snapshot=row.document_metadata_snapshot,
            status_events=[_status_event_view(event) for event in status_events],
            submission_events=[
                SubmissionEventView(
                    id=event.id,
                    evidence_type=event.evidence_type,
                    evidence_source=event.evidence_source,
                    observed_at=event.observed_at,
                    signal_code=event.signal_code,
                    application_id=event.application_id,
                    replayed=False,
                )
                for event in submission_events
            ],
            answers=[
                {
                    "field_key": answer.field_key,
                    "answer_value": answer.answer_value,
                    "provenance": answer.provenance_snapshot,
                }
                for answer in answers
            ],
        )


@router.patch("/applications/{application_id}", response_model=ApplicationView)
def patch_application(
    application_id: UUID,
    body: ApplicationPatch,
    request: Request,
    if_match: str | None = Header(default=None),
    auth: AuthContext = Depends(require_auth),
) -> ApplicationView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_application(session, auth.user_id, application_id)
        _check_revision(row, None, if_match)
        if body.employer is not None:
            row.employer = body.employer
        if body.role is not None:
            row.role = body.role
        if body.follow_up_date is not None:
            row.follow_up_date = body.follow_up_date
        if body.status is not None and body.status != row.status:
            if body.status == "APPLIED" and body.applied_date is None and row.applied_at is None:
                raise HTTPException(
                    status_code=422, detail="applied_date is required to mark applied"
                )
            _record_status(
                session,
                auth.user_id,
                row,
                body.status,
                "USER_CONFIRMATION",
                {"kind": "manual_status_change", "note": body.note},
            )
            if body.applied_date is not None:
                row.applied_date = body.applied_date
        row.revision += 1
        session.flush()
        return _application_view(row)


@router.post("/applications/{application_id}/confirm", response_model=ApplicationView)
def confirm_applied(
    application_id: UUID,
    body: ConfirmAppliedRequest,
    request: Request,
    if_match: str | None = Header(default=None),
    auth: AuthContext = Depends(require_auth),
) -> ApplicationView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = _get_application(session, auth.user_id, application_id)
        _check_revision(row, None, if_match)
        _record_status(
            session,
            auth.user_id,
            row,
            "APPLIED",
            "USER_CONFIRMATION",
            {"kind": "USER_CONFIRMED_FORM", "note": body.note},
        )
        row.applied_date = body.applied_date
        row.revision += 1
        session.flush()
        return _application_view(row)


@router.get("/dashboard", response_model=DashboardView)
def dashboard(auth: AuthContext = Depends(require_auth)) -> DashboardView:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        today_dt = datetime.now(UTC)
        today = today_dt.date()
        prepared = int(
            session.scalar(
                select(func.count())
                .select_from(ApplicationSession)
                .where(
                    ApplicationSession.user_id == auth.user_id,
                    ApplicationSession.state.in_(SESSION_OPEN_STATES),
                    or_(
                        ApplicationSession.expires_at.is_(None),
                        ApplicationSession.expires_at > today_dt,
                    ),
                )
            )
            or 0
        )
        status_rows = session.execute(
            select(Application.status, func.count())
            .where(Application.user_id == auth.user_id)
            .group_by(Application.status)
        ).all()
        follow_ups = session.scalars(
            select(Application)
            .where(
                Application.user_id == auth.user_id,
                Application.follow_up_date.is_not(None),
                Application.follow_up_date <= today + timedelta(days=7),
                Application.status.in_(["SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP"]),
            )
            .order_by(Application.follow_up_date)
            .limit(20)
        ).all()
        recent = session.scalars(
            select(ApplicationStatusEvent)
            .where(ApplicationStatusEvent.user_id == auth.user_id)
            .order_by(ApplicationStatusEvent.occurred_at.desc())
            .limit(10)
        ).all()
        return DashboardView(
            prepared_sessions=prepared,
            applications_by_status={
                status: int(count) for status, count in status_rows
            },
            upcoming_follow_ups=[_application_view(row) for row in follow_ups],
            recent_status_events=[_status_event_view(row) for row in recent],
        )
