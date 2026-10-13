"""Worker loop idle and graceful-shutdown checks without a database dependency."""

from __future__ import annotations

import asyncio
from uuid import uuid4

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
