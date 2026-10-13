"""Worker loop idle and graceful-shutdown checks without a database dependency."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.worker import runner
from app.worker.runner import JobContext


def test_worker_stops_cleanly_while_idle(monkeypatch) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(runner, "_claim", lambda _worker_id: None)
        stop = asyncio.Event()
        asyncio.get_running_loop().call_later(0.02, stop.set)
        await runner.run(stop, worker_id="idle-test")

    asyncio.run(scenario())


def test_worker_shutdown_waits_for_active_job_to_finish(monkeypatch) -> None:
    async def scenario() -> None:
        stop = asyncio.Event()
        started = asyncio.Event()
        release = asyncio.Event()
        job = JobContext(
            id=uuid4(),
            owner_id=uuid4(),
            kind="test-work",
            reference_type=None,
            reference_id=None,
            attempt=1,
        )
        claimed = False

        def claim(_worker_id: str) -> JobContext | None:
            nonlocal claimed
            if claimed:
                return None
            claimed = True
            return job

        async def handle(_job: JobContext, _worker_id: str) -> None:
            started.set()
            await release.wait()

        monkeypatch.setattr(runner, "_claim", claim)
        monkeypatch.setattr(runner, "_run_job", handle)
        task = asyncio.create_task(runner.run(stop, worker_id="shutdown-test"))
        await asyncio.wait_for(started.wait(), timeout=1)
        stop.set()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_worker_retries_transient_claim_failures_but_keeps_role_errors_fatal(monkeypatch) -> None:
    async def scenario() -> None:
        stop = asyncio.Event()
        attempts = 0

        def claim(_worker_id: str) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise SQLAlchemyError("temporary connection failure")
            stop.set()
            return None

        monkeypatch.setattr(runner, "CLAIM_RETRY_DELAY", 0.001)
        monkeypatch.setattr(runner, "_claim", claim)
        await runner.run(stop, worker_id="retry-test")
        assert attempts == 2

    asyncio.run(scenario())

    monkeypatch.setattr(
        runner, "_claim", lambda _worker_id: (_ for _ in ()).throw(RuntimeError("bad role"))
    )
    with pytest.raises(RuntimeError, match="bad role"):
        asyncio.run(runner.run(asyncio.Event(), worker_id="role-test"))


def test_heartbeat_retries_transient_database_error(monkeypatch) -> None:
    async def scenario() -> None:
        job = JobContext(
            id=uuid4(),
            owner_id=uuid4(),
            kind="test-work",
            reference_type=None,
            reference_id=None,
            attempt=1,
        )
        calls = 0

        def heartbeat_once(_job_id, _worker_id) -> bool:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise SQLAlchemyError("temporary connection failure")
            return False

        monkeypatch.setattr(runner, "LEASE_HEARTBEAT", timedelta(milliseconds=1))
        monkeypatch.setattr(runner, "_heartbeat_once", heartbeat_once)
        await runner._heartbeat(job, "heartbeat-test", asyncio.Event())
        assert calls == 2

    asyncio.run(scenario())
