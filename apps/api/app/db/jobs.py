"""PostgreSQL-backed durable job queue primitives."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import Job

LEASE = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def enqueue_job(
    session: Session,
    *,
    owner_id: UUID,
    kind: str,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    next_run_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Job:
    """Persist work in the caller's transaction."""
    if not kind or len(kind) > 64:
        raise ValueError("kind must contain 1 to 64 characters")
    job = Job(
        user_id=owner_id,
        kind=kind,
        reference_type=reference_type,
        reference_id=reference_id,
        next_run_at=next_run_at,
        expires_at=expires_at,
    )
    session.add(job)
    session.flush()
    return job


def claim_next_job(
    session: Session,
    worker_id: str,
    *,
    kinds: Sequence[str] | None = None,
    now: datetime | None = None,
) -> Job | None:
    """Claim one due job, reclaiming an expired lease, with SKIP LOCKED."""
    if not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id must contain 1 to 128 characters")
    moment = now or datetime.now(UTC)
    session.execute(
        update(Job)
        .where(
            Job.state == "RUNNING",
            Job.lease_until <= moment,
            Job.attempts >= MAX_ATTEMPTS,
        )
        .values(
            state="FAILED",
            stage="RETRY_EXHAUSTED",
            lease_owner=None,
            lease_until=None,
            heartbeat_at=None,
        )
    )
    session.execute(
        update(Job)
        .where(
            Job.state == "QUEUED",
            Job.expires_at.is_not(None),
            Job.expires_at <= moment,
        )
        .values(state="FAILED", stage="EXPIRED", next_run_at=None)
    )
    session.execute(
        update(Job)
        .where(
            Job.state == "RUNNING",
            Job.expires_at.is_not(None),
            Job.expires_at <= moment,
        )
        .values(
            state="FAILED",
            stage="EXPIRED",
            lease_owner=None,
            lease_until=None,
            heartbeat_at=None,
            next_run_at=None,
        )
    )
    statement = (
        select(Job)
        .where(
            Job.attempts < MAX_ATTEMPTS,
            or_(Job.next_run_at.is_(None), Job.next_run_at <= moment),
            or_(Job.expires_at.is_(None), Job.expires_at > moment),
            or_(
                Job.state == "QUEUED",
                and_(
                    Job.state == "RUNNING", Job.lease_until.is_not(None), Job.lease_until < moment
                ),
            ),
        )
        .order_by(Job.next_run_at.asc().nullsfirst(), Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if kinds is not None:
        if not kinds:
            return None
        statement = statement.where(Job.kind.in_(kinds))
    job = session.scalar(statement)
    if job is None:
        return None
    job.state = "RUNNING"
    job.lease_owner = worker_id
    job.lease_until = moment + LEASE
    job.heartbeat_at = moment
    job.attempts += 1
    session.flush()
    return job


def heartbeat(
    session: Session, job_id: UUID, worker_id: str, *, now: datetime | None = None
) -> bool:
    moment = now or datetime.now(UTC)
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None or job.state != "RUNNING" or job.lease_owner != worker_id:
        return False
    if job.lease_until is None or job.lease_until < moment:
        return False
    job.heartbeat_at = moment
    job.lease_until = moment + LEASE
    session.flush()
    return True


def finish_job(
    session: Session,
    job_id: UUID,
    worker_id: str,
    *,
    state: str,
    stage: str | None = None,
    now: datetime | None = None,
) -> bool:
    if state not in {"SUCCEEDED", "FAILED", "CANCELED"}:
        raise ValueError("terminal state must be SUCCEEDED, FAILED or CANCELED")
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    moment = now or datetime.now(UTC)
    if (
        job is None
        or job.state != "RUNNING"
        or job.lease_owner != worker_id
        or job.lease_until is None
        or job.lease_until < moment
    ):
        return False
    job.state = state
    job.stage = stage
    job.lease_owner = None
    job.lease_until = None
    job.heartbeat_at = None
    job.next_run_at = None
    session.flush()
    return True


def retry_job(
    session: Session,
    job_id: UUID,
    worker_id: str,
    *,
    delay: timedelta,
    stage: str | None = None,
    now: datetime | None = None,
) -> bool:
    if delay < timedelta(0):
        raise ValueError("retry delay cannot be negative")
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    moment = now or datetime.now(UTC)
    if (
        job is None
        or job.state != "RUNNING"
        or job.lease_owner != worker_id
        or job.lease_until is None
        or job.lease_until < moment
    ):
        return False
    job.state = "FAILED" if job.attempts >= MAX_ATTEMPTS else "QUEUED"
    job.stage = stage
    job.lease_owner = None
    job.lease_until = None
    job.heartbeat_at = None
    job.next_run_at = moment + delay if job.state == "QUEUED" else None
    session.flush()
    return True


def cancel_job(session: Session, *, owner_id: UUID, job_id: UUID) -> bool:
    """Cancel only a job owned by the verified caller; leased workers stop on heartbeat."""
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == owner_id).with_for_update()
    )
    if job is None or job.state not in {"QUEUED", "RUNNING"}:
        return False
    job.state = "CANCELED"
    job.stage = "CANCELED_BY_OWNER"
    job.lease_owner = None
    job.lease_until = None
    job.heartbeat_at = None
    session.flush()
    return True
