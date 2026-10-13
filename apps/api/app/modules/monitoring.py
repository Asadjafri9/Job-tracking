"""Monitored sources, discovered jobs, and notifications (MON-001/004).

Up to five public career-page sources per user. Sources save without consent
but stay setup-required (PAUSED) until the scheduled-check consent is given;
consent is stamped with its source revision so later edits re-require it.
Manual check-now is separate from the daily schedule and capped at three
runs per source per day. Discovered jobs are never applications.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.jobs import enqueue_job
from app.db.models import (
    DiscoveredJob,
    MonitoredSource,
    MonitoringRun,
    Notification,
)
from app.db.tenant import tenant_session
from app.monitoring.fetch import FetchUnsupported, validate_public_url
from app.worker.scheduler import (
    SCAN_JOB_EXPIRY,
    SCAN_JOB_KIND,
    SCAN_JOB_REFERENCE_TYPE,
    next_daily_run_utc,
)

router = APIRouter(prefix="/api/v1", tags=["monitoring"])

MAX_SOURCES = 5
MANUAL_RUNS_PER_DAY = 3
MANUAL_RUN_WINDOW = timedelta(hours=24)


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCreate(StrictModel):
    public_url: str = Field(min_length=8, max_length=2048)
    timezone: str = Field(min_length=1, max_length=64)
    schedule: Literal["DAILY", "MANUAL"] = "DAILY"
    source_kind: Literal["HTML", "RSS", "ATS"] = "HTML"
    region_selector: str | None = Field(default=None, max_length=128)
    scheduled_check_consent: bool = False
    saved_key_consent: bool = False


class SourceUpdate(StrictModel):
    expected_revision: int = Field(ge=1)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    schedule: Literal["DAILY", "MANUAL"] | None = None
    region_selector: str | None = Field(default=None, max_length=128)
    scheduled_check_consent: bool | None = None
    saved_key_consent: bool | None = None
    action: Literal["pause", "resume"] | None = None


class SourceView(StrictModel):
    id: UUID
    public_url: str
    source_kind: str
    state: str
    schedule: str
    timezone: str
    region_selector: str | None
    revision: int
    next_run_at: datetime | None
    last_success_at: datetime | None
    scheduled_check_consented_at: datetime | None
    saved_key_consented_at: datetime | None
    last_error: str | None
    setup_required: bool


class SourceList(StrictModel):
    sources: list[SourceView]


class RunView(StrictModel):
    id: UUID
    source_id: UUID
    run_kind: str
    state: str
    completeness: str
    scheduled_local_date: str | None
    completed_count: int
    discovered_count: int
    started_at: datetime | None
    ended_at: datetime | None
    redacted_error: str | None


class RunList(StrictModel):
    runs: list[RunView]


class JobView(StrictModel):
    id: UUID
    source_id: UUID
    title: str
    employer: str | None
    location: str | None
    is_remote: bool | None
    canonical_job_url: str | None
    match_reason: str | None
    status: str
    meaningful_revision: int
    first_seen_at: datetime
    last_seen_at: datetime


class JobList(StrictModel):
    jobs: list[JobView]


class JobUpdate(StrictModel):
    action: Literal["save", "dismiss", "reopen"]


class NotificationView(StrictModel):
    id: UUID
    kind: str
    content: str
    discovered_job_id: UUID | None
    monitoring_run_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(StrictModel):
    notifications: list[NotificationView]
    unread_count: int


def _validate_timezone(name: str) -> None:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="timezone must be an IANA name") from None


def _validate_source_url(raw: str) -> str:
    try:
        return validate_public_url(raw).url
    except FetchUnsupported as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _get_source(
    session: Session, owner_id: UUID, source_id: UUID, lock: bool = False
) -> MonitoredSource:
    query = select(MonitoredSource).where(
        MonitoredSource.id == source_id,
        MonitoredSource.user_id == owner_id,
        MonitoredSource.state != "DELETED",
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise HTTPException(status_code=404, detail="Monitored source not found")
    return row


def _source_view(session: Session, row: MonitoredSource) -> SourceView:
    last_error = session.scalar(
        select(MonitoringRun.redacted_error)
        .where(
            MonitoringRun.source_id == row.id,
            MonitoringRun.redacted_error.is_not(None),
        )
        .order_by(MonitoringRun.created_at.desc())
        .limit(1)
    )
    setup_required = row.schedule == "DAILY" and (
        row.scheduled_check_consented_at is None or row.consent_revision != row.revision
    )
    return SourceView(
        id=row.id,
        public_url=row.public_url,
        source_kind=row.source_kind,
        state=row.state,
        schedule=row.schedule,
        timezone=row.timezone,
        region_selector=row.region_selector,
        revision=row.revision,
        next_run_at=row.next_run_at,
        last_success_at=row.last_success_at,
        scheduled_check_consented_at=row.scheduled_check_consented_at,
        saved_key_consented_at=row.saved_key_consented_at,
        last_error=last_error,
        setup_required=setup_required,
    )


def _activation_fields(row: MonitoredSource, now: datetime) -> None:
    """Recompute consent scheduling after any change; never silently keeps a
    stale next_run_at when consent or schedule no longer supports it."""
    daily_active = (
        row.schedule == "DAILY"
        and row.scheduled_check_consented_at is not None
        and row.consent_revision == row.revision
    )
    if daily_active and row.state == "ACTIVE":
        row.next_run_at = next_daily_run_utc(row.timezone, now)
    else:
        row.next_run_at = None
        if row.state == "ACTIVE":
            row.state = "PAUSED"


@router.post("/monitored-sources", response_model=SourceView, status_code=201)
def create_source(
    body: SourceCreate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SourceView:
    require_csrf(request, auth)
    public_url = _validate_source_url(body.public_url)
    _validate_timezone(body.timezone)
    if body.saved_key_consent and not body.scheduled_check_consent:
        raise HTTPException(
            status_code=422, detail="saved-key consent requires scheduled-check consent"
        )
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        active_count = session.scalar(
            select(func.count())
            .select_from(MonitoredSource)
            .where(
                MonitoredSource.user_id == auth.user_id,
                MonitoredSource.state != "DELETED",
            )
        )
        if (active_count or 0) >= MAX_SOURCES:
            raise HTTPException(status_code=409, detail="source limit of five reached")
        source = MonitoredSource(
            user_id=auth.user_id,
            public_url=public_url,
            source_kind=body.source_kind,
            schedule=body.schedule,
            timezone=body.timezone,
            region_selector=body.region_selector,
            state="PAUSED",
        )
        if body.scheduled_check_consent:
            source.scheduled_check_consented_at = now
            source.consent_revision = 1
            if body.saved_key_consent:
                source.saved_key_consented_at = now
        session.add(source)
        session.flush()
        if body.schedule == "DAILY" and body.scheduled_check_consent:
            source.state = "ACTIVE"
            source.next_run_at = next_daily_run_utc(source.timezone, now)
        return _source_view(session, source)


@router.get("/monitored-sources", response_model=SourceList)
def list_sources(auth: AuthContext = Depends(require_auth)) -> SourceList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        rows = session.scalars(
            select(MonitoredSource)
            .where(
                MonitoredSource.user_id == auth.user_id,
                MonitoredSource.state != "DELETED",
            )
            .order_by(MonitoredSource.created_at)
        ).all()
        return SourceList(sources=[_source_view(session, row) for row in rows])


@router.get("/monitored-sources/{source_id}", response_model=SourceView)
def get_source(source_id: UUID, auth: AuthContext = Depends(require_auth)) -> SourceView:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        return _source_view(session, _get_source(session, auth.user_id, source_id))


@router.patch("/monitored-sources/{source_id}", response_model=SourceView)
def update_source(
    source_id: UUID,
    body: SourceUpdate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> SourceView:
    require_csrf(request, auth)
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        source = _get_source(session, auth.user_id, source_id, lock=True)
        if source.revision != body.expected_revision:
            raise HTTPException(status_code=409, detail="source changed; reload and retry")
        if body.timezone is not None:
            _validate_timezone(body.timezone)
            source.timezone = body.timezone
        if body.schedule is not None:
            source.schedule = body.schedule
        if body.region_selector is not None:
            source.region_selector = body.region_selector or None
        touched = (
            body.timezone is not None
            or body.schedule is not None
            or body.region_selector is not None
        )
        if touched:
            source.revision += 1
        if body.scheduled_check_consent is True and (
            source.scheduled_check_consented_at is None
            or source.consent_revision != source.revision
        ):
            source.scheduled_check_consented_at = now
            source.consent_revision = source.revision
        elif body.scheduled_check_consent is False:
            source.scheduled_check_consented_at = None
            source.saved_key_consented_at = None
            source.consent_revision = None
        if body.saved_key_consent is True and source.scheduled_check_consented_at is not None:
            source.saved_key_consented_at = now
        elif body.saved_key_consent is False:
            source.saved_key_consented_at = None
        if body.action == "pause":
            source.state = "PAUSED"
        elif body.action == "resume" and source.state in {"PAUSED", "ERROR"}:
            source.state = "ACTIVE"
        _activation_fields(source, now)
        return _source_view(session, source)


@router.delete("/monitored-sources/{source_id}", status_code=204)
def delete_source(
    source_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> None:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        source = _get_source(session, auth.user_id, source_id, lock=True)
        source.state = "DELETED"
        source.next_run_at = None
        source.revision += 1
        session.execute(
            update(MonitoringRun)
            .where(
                MonitoringRun.source_id == source.id,
                MonitoringRun.state == "QUEUED",
            )
            .values(state="CANCELED", redacted_error="source_removed", ended_at=func.now())
        )


@router.post("/monitored-sources/{source_id}/check-now", response_model=RunView, status_code=201)
def check_now(
    source_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> RunView:
    require_csrf(request, auth)
    now = datetime.now(UTC)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        source = _get_source(session, auth.user_id, source_id, lock=True)
        if source.state == "DELETED":
            raise HTTPException(status_code=404, detail="Monitored source not found")
        recent = session.scalar(
            select(func.count())
            .select_from(MonitoringRun)
            .where(
                MonitoringRun.source_id == source.id,
                MonitoringRun.run_kind == "MANUAL",
                MonitoringRun.created_at > now - MANUAL_RUN_WINDOW,
            )
        )
        if (recent or 0) >= MANUAL_RUNS_PER_DAY:
            raise HTTPException(
                status_code=429, detail="manual check limit reached for this source"
            )
        run = MonitoringRun(
            user_id=auth.user_id,
            source_id=source.id,
            request_id=uuid4(),
            schedule_revision=source.revision,
            run_kind="MANUAL",
            state="QUEUED",
            completeness="UNKNOWN",
        )
        session.add(run)
        session.flush()
        enqueue_job(
            session,
            owner_id=auth.user_id,
            kind=SCAN_JOB_KIND,
            reference_type=SCAN_JOB_REFERENCE_TYPE,
            reference_id=run.id,
            expires_at=now + SCAN_JOB_EXPIRY,
        )
        return _run_view(run)


def _run_view(row: MonitoringRun) -> RunView:
    return RunView(
        id=row.id,
        source_id=row.source_id,
        run_kind=row.run_kind,
        state=row.state,
        completeness=row.completeness,
        scheduled_local_date=(
            row.scheduled_local_date.isoformat() if row.scheduled_local_date else None
        ),
        completed_count=row.completed_count,
        discovered_count=row.discovered_count,
        started_at=row.started_at,
        ended_at=row.ended_at,
        redacted_error=row.redacted_error,
    )


@router.get("/monitoring-runs", response_model=RunList)
def list_runs(
    source_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    auth: AuthContext = Depends(require_auth),
) -> RunList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        query = (
            select(MonitoringRun)
            .where(MonitoringRun.user_id == auth.user_id)
            .order_by(MonitoringRun.created_at.desc())
            .limit(limit)
        )
        if source_id is not None:
            query = query.where(MonitoringRun.source_id == source_id)
        return RunList(runs=[_run_view(row) for row in session.scalars(query)])


@router.get("/discovered-jobs", response_model=JobList)
def list_discovered_jobs(
    source_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    auth: AuthContext = Depends(require_auth),
) -> JobList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        query = (
            select(DiscoveredJob)
            .where(DiscoveredJob.user_id == auth.user_id)
            .order_by(DiscoveredJob.first_seen_at.desc())
            .limit(limit)
        )
        if source_id is not None:
            query = query.where(DiscoveredJob.source_id == source_id)
        if status is not None:
            query = query.where(DiscoveredJob.status == status)
        rows = session.scalars(query).all()
        return JobList(
            jobs=[
                JobView(
                    id=row.id,
                    source_id=row.source_id,
                    title=row.title,
                    employer=row.employer,
                    location=row.location,
                    is_remote=row.is_remote,
                    canonical_job_url=row.canonical_job_url,
                    match_reason=row.match_reason,
                    status=row.status,
                    meaningful_revision=row.meaningful_revision,
                    first_seen_at=row.first_seen_at,
                    last_seen_at=row.last_seen_at,
                )
                for row in rows
            ]
        )


@router.patch("/discovered-jobs/{job_id}", response_model=JobView)
def update_discovered_job(
    job_id: UUID,
    body: JobUpdate,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> JobView:
    require_csrf(request, auth)
    transitions = {"save": "SAVED", "dismiss": "DISMISSED", "reopen": "NEW"}
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(DiscoveredJob)
            .where(
                DiscoveredJob.id == job_id,
                DiscoveredJob.user_id == auth.user_id,
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Discovered job not found")
        if row.status == "CLOSED" and body.action != "reopen":
            raise HTTPException(status_code=409, detail="closed jobs can only be reopened")
        row.status = transitions[body.action]
        session.flush()
        return JobView(
            id=row.id,
            source_id=row.source_id,
            title=row.title,
            employer=row.employer,
            location=row.location,
            is_remote=row.is_remote,
            canonical_job_url=row.canonical_job_url,
            match_reason=row.match_reason,
            status=row.status,
            meaningful_revision=row.meaningful_revision,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
        )


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    unread: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    auth: AuthContext = Depends(require_auth),
) -> NotificationList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        query = (
            select(Notification)
            .where(Notification.user_id == auth.user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread:
            query = query.where(Notification.read_at.is_(None))
        rows = session.scalars(query).all()
        unread_count = session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == auth.user_id,
                Notification.read_at.is_(None),
            )
        )
        return NotificationList(
            notifications=[
                NotificationView(
                    id=row.id,
                    kind=row.kind,
                    content=row.content,
                    discovered_job_id=row.discovered_job_id,
                    monitoring_run_id=row.monitoring_run_id,
                    read_at=row.read_at,
                    created_at=row.created_at,
                )
                for row in rows
            ],
            unread_count=unread_count or 0,
        )


@router.post("/notifications/{notification_id}/read", response_model=NotificationView)
def mark_notification_read(
    notification_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> NotificationView:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        row = session.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == auth.user_id,
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        if row.read_at is None:
            row.read_at = datetime.now(UTC)
        return NotificationView(
            id=row.id,
            kind=row.kind,
            content=row.content,
            discovered_job_id=row.discovered_job_id,
            monitoring_run_id=row.monitoring_run_id,
            read_at=row.read_at,
            created_at=row.created_at,
        )


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> None:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        session.execute(
            update(Notification)
            .where(
                Notification.user_id == auth.user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
        )
