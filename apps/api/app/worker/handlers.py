"""Registered durable workload handlers.

Handlers run inside an owner-scoped runtime transaction derived from the
trusted job row; they never accept an owner from the job body. The daily
scan handler performs the claim-time revalidation required by the
monitoring contract and records an honest outcome until the fetch/match
pipeline lands in M5.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import (
    ExtensionGrant,
    IdempotencyRecord,
    MonitoredSource,
    MonitoringRun,
    QuotaReservation,
)
from app.db.models import Session as SessionRecord
from app.db.tenant import tenant_session
from app.worker.registry import HANDLERS, JobContext, register
from app.worker.scheduler import SCAN_JOB_KIND, SCAN_JOB_REFERENCE_TYPE

logger = logging.getLogger("app.worker.handlers")

CLEANUP_JOB_KIND = "maintenance.owner_cleanup"
PIPELINE_PENDING_REASON = "daily_scan_pipeline_pending_m5"
SOURCE_STALE_REASON = "source_schedule_or_consent_changed"

OwnerWork = Callable[[OrmSession, JobContext], None]


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


def _daily_scan(session: OrmSession, context: JobContext) -> None:
    """Revalidate a dispatched daily run before any fetch/provider work."""
    now = datetime.now(UTC)
    if context.reference_type != SCAN_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("daily scan jobs must reference a monitoring run")
    run = session.scalar(
        select(MonitoringRun)
        .where(
            MonitoringRun.id == context.reference_id,
            MonitoringRun.user_id == context.owner_id,
        )
        .with_for_update()
    )
    if run is None or run.state != "QUEUED":
        return
    source = session.scalar(
        select(MonitoredSource).where(
            MonitoredSource.id == run.source_id,
            MonitoredSource.user_id == context.owner_id,
        )
    )
    still_scheduled = (
        source is not None
        and source.state == "ACTIVE"
        and source.schedule == "DAILY"
        and source.scheduled_check_consented_at is not None
        and source.consent_revision is not None
        and source.revision == run.schedule_revision
    )
    run.started_at = now
    run.ended_at = now
    if not still_scheduled:
        run.state = "CANCELED"
        run.redacted_error = SOURCE_STALE_REASON
        logger.info(
            "daily scan canceled before dispatch: run=%s source stale or unconsented", run.id
        )
        return
    run.state = "FAILED"
    run.completeness = "UNKNOWN"
    run.redacted_error = PIPELINE_PENDING_REASON
    logger.info("daily scan run %s recorded pending pipeline implementation", run.id)


def _owner_cleanup(session: OrmSession, context: JobContext) -> None:
    """Purge expired ephemeral records owned by the job's verified owner."""
    now = datetime.now(UTC)
    session.execute(
        delete(ExtensionGrant).where(
            ExtensionGrant.user_id == context.owner_id,
            or_(
                ExtensionGrant.consumed_at.is_not(None),
                ExtensionGrant.revoked_at.is_not(None),
                ExtensionGrant.expires_at <= now,
            ),
        )
    )
    session.execute(
        delete(SessionRecord).where(
            SessionRecord.user_id == context.owner_id,
            or_(SessionRecord.revoked_at.is_not(None), SessionRecord.expires_at <= now),
        )
    )
    session.execute(
        delete(IdempotencyRecord).where(
            IdempotencyRecord.user_id == context.owner_id,
            IdempotencyRecord.expires_at <= now,
        )
    )
    session.execute(
        delete(QuotaReservation).where(
            QuotaReservation.user_id == context.owner_id,
            QuotaReservation.expires_at <= now,
        )
    )


async def _run_owner_scoped(context: JobContext, work: OwnerWork) -> None:
    def execute() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            work(session, context)

    await asyncio.to_thread(execute)


async def handle_daily_scan(context: JobContext, _stopped: asyncio.Event) -> None:
    await _run_owner_scoped(context, _daily_scan)


async def handle_owner_cleanup(context: JobContext, _stopped: asyncio.Event) -> None:
    await _run_owner_scoped(context, _owner_cleanup)


def register_builtin_handlers() -> None:
    """Register durable workload handlers once per worker process."""
    if SCAN_JOB_KIND not in HANDLERS:
        register(SCAN_JOB_KIND, handle_daily_scan)
    if CLEANUP_JOB_KIND not in HANDLERS:
        register(CLEANUP_JOB_KIND, handle_owner_cleanup)
