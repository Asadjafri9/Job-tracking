"""PostgreSQL integration checks for durable job leases and worker isolation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.connection import sqlalchemy_url
from app.db.jobs import (
    LEASE,
    MAX_ATTEMPTS,
    cancel_job,
    claim_next_job,
    enqueue_job,
    finish_job,
    heartbeat,
    retry_job,
)
from app.db.models import Job, Profile, User

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
WORKER_URL = os.getenv("DB002_WORKER_DATABASE_URL")
if MIGRATION_URL is None or WORKER_URL is None:
    pytest.skip("database role URLs are not configured", allow_module_level=True)
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, WORKER_URL)
):
    pytest.skip("job queue tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
worker_engine: Engine = create_engine(sqlalchemy_url(WORKER_URL), pool_pre_ping=True)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://jobs.local.test/issuer",
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


def _enqueue(owner: UUID, kind: str = "unit.test") -> UUID:
    with Session(migration_engine) as session, session.begin():
        return enqueue_job(session, owner_id=owner, kind=kind).id


def test_worker_reclaims_abandoned_lease_after_restart(owner_id: UUID) -> None:
    job_id = _enqueue(owner_id)
    started = datetime.now(UTC)
    with Session(worker_engine) as session, session.begin():
        first = claim_next_job(session, "worker-before-restart", now=started)
        assert first is not None and first.id == job_id and first.attempts == 1

    restarted_at = started + LEASE + timedelta(seconds=1)
    with Session(worker_engine) as session, session.begin():
        reclaimed = claim_next_job(session, "worker-after-restart", now=restarted_at)
        assert reclaimed is not None and reclaimed.id == job_id and reclaimed.attempts == 2
        assert heartbeat(session, job_id, "worker-after-restart", now=restarted_at)
        assert finish_job(session, job_id, "worker-after-restart", state="SUCCEEDED")

    with Session(migration_engine) as session:
        job = session.get(Job, job_id)
        assert job is not None and job.state == "SUCCEEDED" and job.lease_owner is None


def test_worker_retries_then_exhausts_at_attempt_limit(owner_id: UUID) -> None:
    job_id = _enqueue(owner_id)
    now = datetime.now(UTC)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        with Session(worker_engine) as session, session.begin():
            job = claim_next_job(session, "retry-worker", now=now)
            assert job is not None and job.id == job_id and job.attempts == attempt
            assert retry_job(
                session,
                job_id,
                "retry-worker",
                delay=timedelta(0),
                stage="RETRY_EXHAUSTED" if attempt == MAX_ATTEMPTS else "RETRYING",
                now=now,
            )
        now += timedelta(seconds=1)

    with Session(migration_engine) as session:
        job = session.get(Job, job_id)
        assert job is not None and job.state == "FAILED" and job.stage == "RETRY_EXHAUSTED"


def test_worker_skips_locked_jobs_and_cannot_read_owner_data(owner_id: UUID) -> None:
    first_id = _enqueue(owner_id, "unit.concurrent")
    second_id = _enqueue(owner_id, "unit.concurrent")
    with Session(worker_engine) as session:
        with pytest.raises(ProgrammingError):
            session.scalar(select(User.id).where(User.id == owner_id))
    barrier = Barrier(2)

    def claim(worker: str) -> UUID:
        with Session(worker_engine) as session, session.begin():
            job = claim_next_job(session, worker, kinds=("unit.concurrent",))
            assert job is not None
            barrier.wait(timeout=5)
            return job.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = set(pool.map(claim, ("worker-one", "worker-two")))
    assert claimed == {first_id, second_id}


def test_owner_cancellation_is_scoped_and_prevents_future_claims(owner_id: UUID) -> None:
    job_id = _enqueue(owner_id)
    with Session(migration_engine) as session, session.begin():
        assert cancel_job(session, owner_id=owner_id, job_id=job_id)
    with Session(worker_engine) as session, session.begin():
        assert claim_next_job(session, "cancel-worker") is None
