"""Owner-scoped idempotency and optimistic revision helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord, Profile, QuotaReservation


class IdempotencyConflict(ValueError):
    """An idempotency key was reused with a different normalized request."""


@dataclass(frozen=True)
class IdempotencyResult:
    record: IdempotencyRecord
    created: bool


def fingerprint(secret: bytes, normalized_input: object) -> str:
    """HMAC normalized request metadata; callers must omit secrets and raw payloads."""
    canonical = json.dumps(
        normalized_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hmac.new(secret, canonical, hashlib.sha256).hexdigest()


def claim_idempotency(
    session: Session,
    *,
    owner_id: UUID,
    route_key: str,
    key: UUID,
    input_fingerprint: str,
    response_status: int = 202,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    retention: timedelta = timedelta(hours=24),
) -> IdempotencyResult:
    """Atomically reserve a scoped key or return the prior result metadata."""
    if len(input_fingerprint) != 64:
        raise ValueError("input_fingerprint must be a SHA-256 hex digest")
    if retention <= timedelta(0):
        raise ValueError("retention must be positive")
    now = datetime.now(UTC)
    statement = (
        insert(IdempotencyRecord)
        .values(
            user_id=owner_id,
            route_key=route_key,
            idempotency_key=key,
            input_hmac=input_fingerprint,
            entity_type=entity_type,
            entity_id=entity_id,
            response_status=response_status,
            expires_at=now + retention,
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_scope_key")
        .returning(IdempotencyRecord.id)
    )
    inserted_id = session.scalar(statement)
    if inserted_id is not None:
        record = session.scalar(
            select(IdempotencyRecord).where(IdempotencyRecord.id == inserted_id)
        )
        assert record is not None
        return IdempotencyResult(record=record, created=True)

    record = session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.user_id == owner_id,
            IdempotencyRecord.route_key == route_key,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
    )
    if record is None or record.expires_at <= now:
        raise IdempotencyConflict("idempotency key expired; use a new key")
    if not hmac.compare_digest(record.input_hmac, input_fingerprint):
        raise IdempotencyConflict("idempotency key was already used with different input")
    return IdempotencyResult(record=record, created=False)


def require_revision(actual: int, expected: int) -> None:
    """Raise a stable conflict when an If-Match revision is stale."""
    if actual != expected:
        raise IdempotencyConflict("revision conflict")


def conditional_revision_update(
    session: Session,
    *,
    model: type[Any],
    owner_id: UUID,
    entity_id: UUID,
    revision_field: str,
    expected_revision: int,
    values: dict[str, object],
) -> int:
    """Apply a single owner-scoped optimistic update and increment its revision."""
    if revision_field not in model.__table__.columns or "user_id" not in model.__table__.columns:
        raise ValueError("model must have owner and revision columns")
    if revision_field in values or "id" in values or "user_id" in values:
        raise ValueError("caller cannot override identity or revision fields")
    statement = (
        update(model)
        .where(
            model.user_id == owner_id,
            model.id == entity_id,
            getattr(model, revision_field) == expected_revision,
        )
        .values(**values, **{revision_field: expected_revision + 1})
        .returning(getattr(model, revision_field))
    )
    revision = session.scalar(statement)
    if revision is None:
        raise IdempotencyConflict("revision conflict or entity not found")
    return int(revision)


def reserve_quota(
    session: Session,
    *,
    owner_id: UUID,
    kind: str,
    reservation_key: UUID,
    amount: int,
    committed_usage: int,
    maximum: int,
    ttl: timedelta = timedelta(hours=1),
    now: datetime | None = None,
) -> QuotaReservation:
    """Atomically reserve per-owner capacity while a bounded operation runs."""
    if amount <= 0 or committed_usage < 0 or maximum <= 0 or ttl <= timedelta(0):
        raise ValueError("quota values and reservation lifetime must be positive")
    profile = session.scalar(
        select(Profile.id).where(Profile.user_id == owner_id).with_for_update()
    )
    if profile is None:
        raise IdempotencyConflict("owner account not found")
    moment = now or datetime.now(UTC)
    session.execute(
        delete(QuotaReservation).where(
            QuotaReservation.user_id == owner_id,
            QuotaReservation.kind == kind,
            QuotaReservation.expires_at <= moment,
        )
    )
    existing = session.scalar(
        select(QuotaReservation).where(
            QuotaReservation.user_id == owner_id,
            QuotaReservation.kind == kind,
            QuotaReservation.reservation_key == reservation_key,
        )
    )
    if existing is not None:
        if existing.amount != amount:
            raise IdempotencyConflict("reservation key was reused with a different amount")
        return existing
    reserved = int(
        session.scalar(
            select(func.coalesce(func.sum(QuotaReservation.amount), 0)).where(
                QuotaReservation.user_id == owner_id,
                QuotaReservation.kind == kind,
                QuotaReservation.expires_at > moment,
            )
        )
        or 0
    )
    if committed_usage + reserved + amount > maximum:
        raise IdempotencyConflict("quota exceeded")
    reservation = QuotaReservation(
        user_id=owner_id,
        kind=kind,
        reservation_key=reservation_key,
        amount=amount,
        expires_at=moment + ttl,
    )
    session.add(reservation)
    session.flush()
    return reservation


def release_quota(session: Session, *, owner_id: UUID, kind: str, reservation_key: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        session.execute(
            delete(QuotaReservation).where(
                QuotaReservation.user_id == owner_id,
                QuotaReservation.kind == kind,
                QuotaReservation.reservation_key == reservation_key,
            )
        ),
    )
    return bool(result.rowcount)
