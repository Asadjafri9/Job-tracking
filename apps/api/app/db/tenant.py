"""Transaction-scoped tenant context for verified application identities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def _set_tenant_context(session: Session, owner_id: UUID) -> None:
    """Set the owner for the current transaction using a verified UUID."""
    if not isinstance(owner_id, UUID):
        raise TypeError("owner_id must be a verified UUID")
    if not session.in_transaction():
        raise RuntimeError("tenant context must be set inside a transaction")
    database_role = session.scalar(text("SELECT current_user"))
    if database_role != "copilot_runtime":
        raise RuntimeError("tenant sessions require the copilot_runtime database role")
    session.execute(
        text("SELECT set_config('app.user_id', :owner_id, true)"),
        {"owner_id": str(owner_id)},
    )


@contextmanager
def tenant_session(engine: Engine, owner_id: UUID) -> Iterator[Session]:
    """Yield a session scoped to one authenticated owner for one transaction.

    Derive ``owner_id`` from an authenticated server-side session or trusted
    durable job. Never use an ID supplied by the API request body.
    """
    with Session(engine) as session:
        with session.begin():
            _set_tenant_context(session, owner_id)
            yield session
