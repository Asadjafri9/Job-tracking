"""PostgreSQL checks for the daily scheduler tick and registered handlers."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.connection import sqlalchemy_url
from app.db.models import (
    ExtensionGrant,
    IdempotencyRecord,
    Job,
    MonitoredSource,
    MonitoringRun,
    Profile,
    QuotaReservation,
    User,
)
from app.db.models import Session as SessionRecord
from app.worker import handlers, scheduler
from app.worker.runner import JobContext

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
SCHEDULER_URL = os.getenv("JOB001_SCHEDULER_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or SCHEDULER_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "scheduler tests need migration, scheduler, and runtime database URLs",
        allow_module_level=True,
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, SCHEDULER_URL, RUNTIME_URL)
):
    pytest.skip("scheduler tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
scheduler_engine: Engine = create_engine(sqlalchemy_url(SCHEDULER_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)

NOW = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://scheduler.local.test/issuer",
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


@pytest.fixture(autouse=True)
def _runtime_for_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handlers, "_runtime_engine", lambda: runtime_engine)


def _add_source(
    owner: UUID,
    *,
    next_run_at: datetime | None,
    timezone: str = "UTC",
    state: str = "ACTIVE",
) -> UUID:
    source_id = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            MonitoredSource(
                id=source_id,
                user_id=owner,
                public_url="https://jobs.example.test/careers",
                source_kind="HTML",
                state=state,
                schedule="DAILY",
                timezone=timezone,
                revision=1,
                next_run_at=next_run_at,
                scheduled_check_consented_at=NOW - timedelta(days=1),
                consent_revision=1,
            )
        )
    return source_id


def _runs(source_id: UUID) -> list[MonitoringRun]:
    with Session(migration_engine) as session:
        return list(
            session.scalars(select(MonitoringRun).where(MonitoringRun.source_id == source_id)).all()
        )


def _owner_jobs(owner: UUID) -> list[Job]:
    with Session(migration_engine) as session:
        return list(session.scalars(select(Job).where(Job.user_id == owner)).all())


def _context(owner: UUID, run_id: UUID | None, kind: str) -> JobContext:
    return JobContext(
        id=uuid4(),
        owner_id=owner,
        kind=kind,
        reference_type=scheduler.SCAN_JOB_REFERENCE_TYPE if run_id else None,
        reference_id=run_id,
        attempt=1,
    )


def test_tick_dispatches_due_daily_source_once(owner_id: UUID) -> None:
    due = NOW - timedelta(minutes=1)
    source_id = _add_source(owner_id, next_run_at=due)

    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 0

    runs = _runs(source_id)
    assert len(runs) == 1
    run = runs[0]
    assert run.run_kind == "DAILY" and run.state == "QUEUED"
    assert run.scheduled_local_date == due.astimezone(ZoneInfo("UTC")).date()
    assert run.schedule_revision == 1

    jobs = _owner_jobs(owner_id)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.kind == scheduler.SCAN_JOB_KIND
    assert job.reference_type == scheduler.SCAN_JOB_REFERENCE_TYPE
    assert job.reference_id == run.id and job.state == "QUEUED"

    with Session(migration_engine) as session:
        source = session.get(MonitoredSource, source_id)
        assert source is not None
        assert source.next_run_at == scheduler.next_daily_run_utc("UTC", NOW)
        assert source.next_run_at > NOW


def test_tick_is_atomic_under_concurrent_schedulers(owner_id: UUID) -> None:
    due = NOW - timedelta(minutes=1)
    source_id = _add_source(owner_id, next_run_at=due)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _i: scheduler.dispatch_due_sources(NOW, engine=scheduler_engine),
                range(2),
            )
        )
    assert sum(results) == 1
    assert len(_runs(source_id)) == 1
    assert len(_owner_jobs(owner_id)) == 1


def test_tick_records_missed_slots_and_catches_up_once(owner_id: UUID) -> None:
    # A 25-hour-old slot is outside the six-hour catch-up window; today's slot is inside.
    missed_slot = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    source_id = _add_source(owner_id, next_run_at=missed_slot)

    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    runs = sorted(_runs(source_id), key=lambda run: run.scheduled_local_date or date.min)
    assert [run.state for run in runs] == ["SKIPPED", "QUEUED"]
    skipped, queued = runs
    assert skipped.redacted_error == scheduler.MISSED_SLOT_REASON
    assert skipped.scheduled_local_date == date(2026, 10, 13)
    assert queued.scheduled_local_date == date(2026, 10, 14)
    jobs = _owner_jobs(owner_id)
    assert len(jobs) == 1 and jobs[0].reference_id == queued.id


def test_tick_never_enqueues_slots_outside_catch_up_window(
    owner_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With two slots older than six hours, the per-tick bound must leave the
    # second stale slot for a later tick instead of enqueueing it.
    monkeypatch.setattr(scheduler, "MAX_MISSED_SLOTS_PER_SOURCE", 1)
    source_id = _add_source(owner_id, next_run_at=datetime(2026, 10, 12, 9, 0, tzinfo=UTC))

    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    assert [run.state for run in _runs(source_id)] == ["SKIPPED"]
    assert _owner_jobs(owner_id) == []
    with Session(migration_engine) as session:
        source = session.get(MonitoredSource, source_id)
        assert source is not None
        assert source.next_run_at == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)

    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    states = sorted(run.state for run in _runs(source_id))
    assert states == ["QUEUED", "SKIPPED", "SKIPPED"]
    jobs = _owner_jobs(owner_id)
    assert len(jobs) == 1
    queued = next(run for run in _runs(source_id) if run.state == "QUEUED")
    assert jobs[0].reference_id == queued.id


def test_tick_marks_unknown_timezone_source_error(owner_id: UUID) -> None:
    source_id = _add_source(
        owner_id,
        next_run_at=NOW - timedelta(minutes=1),
        timezone="Not/AZone",
    )
    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    with Session(migration_engine) as session:
        source = session.get(MonitoredSource, source_id)
        assert source is not None and source.state == "ERROR" and source.next_run_at is None
    assert _runs(source_id) == []


def test_scheduler_role_cannot_read_owner_data_or_delete_sources(owner_id: UUID) -> None:
    _add_source(owner_id, next_run_at=NOW + timedelta(hours=1))
    with Session(scheduler_engine) as session:
        with pytest.raises(ProgrammingError):
            session.scalar(select(func.count()).select_from(Profile))
        session.rollback()
        with pytest.raises(ProgrammingError):
            session.execute(text("UPDATE monitored_sources SET state = 'DELETED'"))
        session.rollback()


def test_daily_scan_handler_cancels_when_source_no_longer_scheduled(
    owner_id: UUID,
) -> None:
    source_id = _add_source(owner_id, next_run_at=NOW - timedelta(minutes=1))
    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    run = _runs(source_id)[0]
    with Session(migration_engine) as session, session.begin():
        source = session.get(MonitoredSource, source_id)
        assert source is not None
        source.revision += 1

    asyncio.run(
        handlers.handle_daily_scan(
            _context(owner_id, run.id, scheduler.SCAN_JOB_KIND), asyncio.Event()
        )
    )

    with Session(migration_engine) as session:
        stored = session.get(MonitoringRun, run.id)
        assert stored is not None
        assert stored.state == "CANCELED"
        assert stored.redacted_error == handlers.SOURCE_STALE_REASON


def test_daily_scan_handler_records_fetch_failure(owner_id: UUID) -> None:
    """An unresolvable source is recorded FAILED, never fabricated."""
    source_id = _add_source(owner_id, next_run_at=NOW - timedelta(minutes=1))
    assert scheduler.dispatch_due_sources(NOW, engine=scheduler_engine) == 1
    run = _runs(source_id)[0]
    asyncio.run(
        handlers.handle_daily_scan(
            _context(owner_id, run.id, scheduler.SCAN_JOB_KIND), asyncio.Event()
        )
    )
    with Session(migration_engine) as session:
        stored = session.get(MonitoringRun, run.id)
        assert stored is not None
        assert stored.state == "FAILED"
        assert (stored.redacted_error or "").startswith("fetch_error")


def test_owner_cleanup_handler_purges_only_expired_owner_rows(owner_id: UUID) -> None:
    other_id = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=other_id,
                issuer="https://scheduler.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{other_id}@example.test",
                login_email_verified=True,
            )
        )
        session.add(Profile(user_id=other_id))
    try:
        stale = datetime.now(UTC) - timedelta(hours=1)
        live = datetime.now(UTC) + timedelta(hours=1)
        with Session(migration_engine) as session, session.begin():
            for owner in (owner_id, other_id):
                session.add(
                    IdempotencyRecord(
                        user_id=owner,
                        route_key="cleanup.test",
                        idempotency_key=uuid4(),
                        input_hmac="a" * 64,
                        response_status=200,
                        expires_at=stale,
                    )
                )
                session.add(
                    QuotaReservation(
                        user_id=owner,
                        kind="cleanup.test",
                        reservation_key=uuid4(),
                        amount=1,
                        expires_at=stale,
                    )
                )
            session.add(
                IdempotencyRecord(
                    user_id=owner_id,
                    route_key="cleanup.test",
                    idempotency_key=uuid4(),
                    input_hmac="b" * 64,
                    response_status=200,
                    expires_at=live,
                )
            )
            expired_session = SessionRecord(
                user_id=owner_id,
                token_hash="c" * 64,
                client_type="WEB",
                auth_time=stale - timedelta(hours=2),
                last_seen_at=stale - timedelta(hours=2),
                expires_at=stale,
            )
            session.add(expired_session)
            session.flush()
            session.add(
                ExtensionGrant(
                    user_id=owner_id,
                    session_id=expired_session.id,
                    grant_hash="d" * 64,
                    client_id="job-tracking-extension",
                    extension_id="a" * 32,
                    pkce_challenge="e" * 43,
                    state_hash="f" * 64,
                    expires_at=live,
                    revoked_at=stale,
                )
            )

        asyncio.run(
            handlers.handle_owner_cleanup(
                _context(owner_id, None, handlers.CLEANUP_JOB_KIND), asyncio.Event()
            )
        )

        with Session(migration_engine) as session:
            remaining = session.scalars(
                select(IdempotencyRecord).where(IdempotencyRecord.user_id == owner_id)
            ).all()
            assert len(remaining) == 1
            assert (
                session.scalars(
                    select(QuotaReservation).where(QuotaReservation.user_id == owner_id)
                ).all()
                == []
            )
            assert (
                session.scalars(
                    select(SessionRecord).where(SessionRecord.user_id == owner_id)
                ).all()
                == []
            )
            assert (
                session.scalars(
                    select(ExtensionGrant).where(ExtensionGrant.user_id == owner_id)
                ).all()
                == []
            )
            other_expired = session.scalars(
                select(IdempotencyRecord).where(IdempotencyRecord.user_id == other_id)
            ).all()
            assert len(other_expired) == 1
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == other_id))


def test_builtin_handlers_register_once() -> None:
    handlers.register_builtin_handlers()
    handlers.register_builtin_handlers()
    from app.worker.runner import HANDLERS

    assert HANDLERS[scheduler.SCAN_JOB_KIND] is handlers.handle_daily_scan
    assert HANDLERS[handlers.CLEANUP_JOB_KIND] is handlers.handle_owner_cleanup
