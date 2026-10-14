"""Restart-safe worker loop for registered durable job handlers."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from datetime import timedelta
from functools import lru_cache
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.jobs import claim_next_job, finish_job, heartbeat, retry_job
from app.db.models import Job
from app.worker.registry import HANDLERS, JobContext, register  # noqa: F401  (re-exported)

logger = logging.getLogger("app.worker")
LEASE_HEARTBEAT = timedelta(seconds=20)
MAX_RUNTIME = 15 * 60
MAX_CONCURRENCY = 4
CLAIM_RETRY_DELAY = 5.0


@lru_cache(maxsize=1)
def _worker_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().worker_database_url), pool_pre_ping=True)


def _context(job: Job) -> JobContext:
    return JobContext(
        id=job.id,
        owner_id=job.user_id,
        kind=job.kind,
        reference_type=job.reference_type,
        reference_id=job.reference_id,
        attempt=job.attempts,
    )


def _claim(worker_id: str) -> JobContext | None:
    engine = _worker_engine()
    with Session(engine) as session, session.begin():
        role = session.scalar(text("SELECT current_user"))
        if role != "copilot_worker":
            raise RuntimeError("worker must use the copilot_worker database role")
        job = claim_next_job(session, worker_id, kinds=tuple(HANDLERS))
        return _context(job) if job is not None else None


def _heartbeat_once(job_id: UUID, worker_id: str) -> bool:
    with Session(_worker_engine()) as session, session.begin():
        return heartbeat(session, job_id, worker_id)


def _finish(job_id: UUID, worker_id: str, *, state: str, stage: str | None = None) -> None:
    with Session(_worker_engine()) as session, session.begin():
        finish_job(session, job_id, worker_id, state=state, stage=stage)


def _retry(job_id: UUID, worker_id: str, *, delay: timedelta, stage: str) -> None:
    with Session(_worker_engine()) as session, session.begin():
        retry_job(session, job_id, worker_id, delay=delay, stage=stage)


async def _heartbeat(job: JobContext, worker_id: str, stopped: asyncio.Event) -> None:
    while not stopped.is_set():
        try:
            await asyncio.wait_for(stopped.wait(), timeout=LEASE_HEARTBEAT.total_seconds())
            return
        except TimeoutError:
            pass
        try:
            still_owned = await asyncio.to_thread(_heartbeat_once, job.id, worker_id)
        except SQLAlchemyError:
            logger.exception("job heartbeat failed; will retry")
            continue
        if not still_owned:
            stopped.set()
            return


async def _run_job(job: JobContext, worker_id: str) -> None:
    handler = HANDLERS.get(job.kind)
    if handler is None:
        await asyncio.to_thread(_finish, job.id, worker_id, state="FAILED", stage="NO_HANDLER")
        logger.error("job failed with no handler: kind=%s id=%s", job.kind, job.id)
        return

    stop_heartbeat = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(job, worker_id, stop_heartbeat))
    handler_task = asyncio.create_task(
        asyncio.wait_for(handler(job, stop_heartbeat), timeout=MAX_RUNTIME)
    )
    try:
        done, _ = await asyncio.wait(
            {handler_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if heartbeat_task in done and not handler_task.done():
            handler_task.cancel()
            await asyncio.gather(handler_task, return_exceptions=True)
            return
        await handler_task
    except asyncio.CancelledError:
        await asyncio.to_thread(
            _retry,
            job.id,
            worker_id,
            delay=timedelta(seconds=0),
            stage="WORKER_RESTART",
        )
        raise
    except Exception as error:
        delay = min(30 * (2 ** max(0, job.attempt - 1)), 1800)
        await asyncio.to_thread(
            _retry,
            job.id,
            worker_id,
            delay=timedelta(seconds=delay),
            stage="RETRYING" if job.attempt < 5 else "RETRY_EXHAUSTED",
        )
        logger.warning(
            "job attempt failed: kind=%s id=%s error=%s", job.kind, job.id, type(error).__name__
        )
    else:
        await asyncio.to_thread(_finish, job.id, worker_id, state="SUCCEEDED", stage="COMPLETE")
    finally:
        stop_heartbeat.set()
        await heartbeat_task


async def run(stop: asyncio.Event, *, worker_id: str | None = None) -> None:
    """Claim jobs with bounded concurrency until stopped."""
    identity = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    active: set[asyncio.Task[None]] = set()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def run_limited(job: JobContext) -> None:
        async with semaphore:
            await _run_job(job, identity)

    while not stop.is_set() or active:
        active = {task for task in active if not task.done()}
        if not stop.is_set() and len(active) < MAX_CONCURRENCY:
            try:
                job = await asyncio.to_thread(_claim, identity)
            except SQLAlchemyError:
                logger.exception("job claim failed; backing off before retry")
                job = None
                try:
                    await asyncio.wait_for(stop.wait(), timeout=CLAIM_RETRY_DELAY)
                except TimeoutError:
                    pass
            if job is not None:
                active.add(asyncio.create_task(run_limited(job)))
                continue
        if active:
            await asyncio.wait(active, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
        elif not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except TimeoutError:
                pass


async def main() -> None:
    from app.worker.handlers import register_builtin_handlers

    register_builtin_handlers()
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
