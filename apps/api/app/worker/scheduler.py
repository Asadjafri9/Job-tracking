"""Restart-safe daily scheduler for monitored sources.

Every minute the scheduler claims due ACTIVE daily sources, records one
unique ``(source_id, scheduled_local_date)`` monitoring run, enqueues the
matching durable scan job, and advances ``next_run_at`` to the next 09:00
slot in the source's IANA timezone. A restart catches up at most one missed
slot inside a six-hour window; older slots are recorded SKIPPED so missed
days stay visible without replaying stale scans.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import create_engine, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import Job, MonitoredSource, MonitoringRun

logger = logging.getLogger("app.scheduler")

DAILY_LOCAL_TIME = time(9, 0)
TICK_INTERVAL = timedelta(minutes=1)
CATCH_UP_WINDOW = timedelta(hours=6)
MAX_MISSED_SLOTS_PER_SOURCE = 32
MAX_SOURCES_PER_TICK = 200
SCAN_JOB_KIND = "monitoring.daily_scan"
SCAN_JOB_EXPIRY = timedelta(minutes=30)
SCAN_JOB_REFERENCE_TYPE = "monitoring_run"
MISSED_SLOT_REASON = "missed_dispatch_window"


def _resolve_local_slot(tz: ZoneInfo, day: date) -> datetime:
    """Return the UTC instant of 09:00 local on ``day``.

    Ambiguous local times resolve to the earliest occurrence (fold=0);
    nonexistent local times resolve to the next valid instant, per the
    monitoring contract's DST rules.
    """
    naive = datetime.combine(day, DAILY_LOCAL_TIME)
    for offset in range(0, 24 * 60 + 1):
        probe = naive + timedelta(minutes=offset)
        aware = probe.replace(tzinfo=tz, fold=0)
        if aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None) == probe:
            return aware.astimezone(UTC)
    raise ValueError(f"no valid local slot within 24h for {tz} on {day}")


def next_daily_run_utc(tz_name: str, after_utc: datetime) -> datetime:
    """Next 09:00-local instant in ``tz_name`` strictly after ``after_utc``."""
    tz = ZoneInfo(tz_name)
    moment = after_utc.astimezone(UTC)
    day = moment.astimezone(tz).date()
    slot = _resolve_local_slot(tz, day)
    while slot <= moment:
        day += timedelta(days=1)
        slot = _resolve_local_slot(tz, day)
    return slot


@lru_cache(maxsize=1)
def _scheduler_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().scheduler_database_url), pool_pre_ping=True)


def _insert_run(
    session: Session, source_id: UUID, user_id: UUID, revision: int, local_date: date
) -> MonitoringRun | None:
    """Insert the unique daily run for ``local_date``; return the stored row."""
    run_id = session.scalar(
        pg_insert(MonitoringRun)
        .values(
            user_id=user_id,
            source_id=source_id,
            schedule_revision=revision,
            run_kind="DAILY",
            scheduled_local_date=local_date,
            state="QUEUED",
            completeness="UNKNOWN",
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "source_id", "scheduled_local_date"],
            index_where=text("run_kind = 'DAILY'"),
        )
        .returning(MonitoringRun.id)
    )
    if run_id is not None:
        return session.get(MonitoringRun, run_id)
    return session.scalar(
        select(MonitoringRun).where(
            MonitoringRun.user_id == user_id,
            MonitoringRun.source_id == source_id,
            MonitoringRun.run_kind == "DAILY",
            MonitoringRun.scheduled_local_date == local_date,
        )
    )


def _insert_skipped_run(
    session: Session,
    source_id: UUID,
    user_id: UUID,
    revision: int,
    slot: datetime,
    local_date: date,
) -> None:
    """Record a missed slot as SKIPPED; a run already recorded for the date wins."""
    session.execute(
        pg_insert(MonitoringRun)
        .values(
            user_id=user_id,
            source_id=source_id,
            schedule_revision=revision,
            run_kind="DAILY",
            scheduled_local_date=local_date,
            state="SKIPPED",
            completeness="UNKNOWN",
            started_at=slot,
            ended_at=slot,
            redacted_error=MISSED_SLOT_REASON,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "source_id", "scheduled_local_date"],
            index_where=text("run_kind = 'DAILY'"),
        )
    )


def _enqueue_scan_job(session: Session, user_id: UUID, run_id: UUID, now: datetime) -> None:
    """Enqueue at most one active scan job per monitoring run."""
    session.execute(
        pg_insert(Job)
        .values(
            user_id=user_id,
            kind=SCAN_JOB_KIND,
            reference_type=SCAN_JOB_REFERENCE_TYPE,
            reference_id=run_id,
            next_run_at=None,
            expires_at=now + SCAN_JOB_EXPIRY,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "kind", "reference_id"],
            index_where=text("state IN ('QUEUED','RUNNING') AND reference_id IS NOT NULL"),
        )
    )


def _dispatch_source(session: Session, source_id: UUID, now: datetime) -> bool:
    """Dispatch one source inside its own transaction; returns True if advanced."""
    source = session.execute(
        select(
            MonitoredSource.id,
            MonitoredSource.user_id,
            MonitoredSource.timezone,
            MonitoredSource.next_run_at,
            MonitoredSource.revision,
        )
        .where(
            MonitoredSource.id == source_id,
            MonitoredSource.state == "ACTIVE",
            MonitoredSource.schedule == "DAILY",
            MonitoredSource.next_run_at.is_not(None),
            MonitoredSource.next_run_at <= now,
            MonitoredSource.scheduled_check_consented_at.is_not(None),
            MonitoredSource.consent_revision.is_not(None),
        )
        .with_for_update()
    ).one_or_none()
    if source is None:
        return False

    try:
        tz = ZoneInfo(source.timezone)
    except ZoneInfoNotFoundError:
        session.execute(
            update(MonitoredSource)
            .where(MonitoredSource.id == source.id)
            .values(state="ERROR", next_run_at=None, updated_at=now)
        )
        logger.error("source %s has invalid timezone %s", source.id, source.timezone)
        return True

    slot = source.next_run_at
    missed = 0
    while slot <= now and now - slot > CATCH_UP_WINDOW and missed < MAX_MISSED_SLOTS_PER_SOURCE:
        _insert_skipped_run(
            session,
            source.id,
            source.user_id,
            source.revision,
            slot,
            slot.astimezone(tz).date(),
        )
        slot = next_daily_run_utc(source.timezone, slot)
        missed += 1

    if slot <= now and now - slot <= CATCH_UP_WINDOW:
        run = _insert_run(
            session, source.id, source.user_id, source.revision, slot.astimezone(tz).date()
        )
        if run is not None and run.state in {"QUEUED", "RUNNING"}:
            _enqueue_scan_job(session, source.user_id, run.id, now)
        slot = next_daily_run_utc(source.timezone, slot)

    session.execute(
        update(MonitoredSource)
        .where(MonitoredSource.id == source.id)
        .values(next_run_at=slot, updated_at=now)
    )
    return True


def dispatch_due_sources(now: datetime | None = None, engine: Engine | None = None) -> int:
    """One scheduler tick: atomically dispatch every due daily source.

    Returns the number of sources whose schedules were advanced.
    """
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    target = engine or _scheduler_engine()
    with Session(target) as session:
        if session.scalar(text("SELECT current_user")) != "copilot_scheduler":
            raise RuntimeError("scheduler must use the copilot_scheduler database role")
        due = session.scalars(
            select(MonitoredSource.id)
            .where(
                MonitoredSource.state == "ACTIVE",
                MonitoredSource.schedule == "DAILY",
                MonitoredSource.next_run_at.is_not(None),
                MonitoredSource.next_run_at <= moment,
                MonitoredSource.scheduled_check_consented_at.is_not(None),
                MonitoredSource.consent_revision.is_not(None),
            )
            .order_by(MonitoredSource.next_run_at.asc())
            .with_for_update(skip_locked=True)
            .limit(MAX_SOURCES_PER_TICK)
        ).all()
    dispatched = 0
    for source_id in due:
        try:
            with Session(target) as session, session.begin():
                if _dispatch_source(session, source_id, moment):
                    dispatched += 1
        except SQLAlchemyError:
            logger.exception("failed to dispatch monitored source %s", source_id)
    return dispatched


async def run(stop: asyncio.Event, *, scheduler_id: str | None = None) -> None:
    """Run one-minute dispatch ticks until stopped."""
    _identity = scheduler_id or f"{socket.gethostname()}:{os.getpid()}"
    while not stop.is_set():
        try:
            await asyncio.to_thread(dispatch_due_sources)
        except SQLAlchemyError:
            logger.exception("scheduler tick failed; retrying next tick")
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_INTERVAL.total_seconds())
        except TimeoutError:
            pass


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows event loops do not expose add_signal_handler.
            signal.signal(sig, lambda _signum, _frame: loop.call_soon_threadsafe(stop.set))
    await run(stop)


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(main())
