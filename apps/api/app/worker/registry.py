"""Shared job-handler registry and claimed-job context."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class JobContext:
    id: UUID
    owner_id: UUID
    kind: str
    reference_type: str | None
    reference_id: UUID | None
    attempt: int


Handler = Callable[[JobContext, asyncio.Event], Awaitable[None]]
HANDLERS: dict[str, Handler] = {}


def register(kind: str, handler: Handler) -> None:
    if not kind or len(kind) > 64 or kind in HANDLERS:
        raise ValueError("invalid or duplicate job handler")
    HANDLERS[kind] = handler
