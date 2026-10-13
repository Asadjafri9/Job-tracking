"""Opaque browser sessions and one-use extension grants."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session as DbSession

from app.db.models import ExtensionGrant, Session, User

IDLE_TIMEOUT = timedelta(minutes=60)
ABSOLUTE_TIMEOUT = timedelta(hours=12)
EXTENSION_GRANT_TTL = timedelta(seconds=60)


class AuthenticationError(PermissionError):
    """The opaque session or extension grant is missing or no longer valid."""


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    session_id: UUID
    user_id: UUID
    expires_at: datetime


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def csrf_token(session_token: str, hash_key: bytes) -> str:
    return (
        base64.urlsafe_b64encode(
            hmac.new(hash_key, session_token.encode(), hashlib.sha256).digest()
        )
        .decode()
        .rstrip("=")
    )


def verify_csrf(session_token: str, supplied: str, hash_key: bytes) -> bool:
    return hmac.compare_digest(csrf_token(session_token, hash_key), supplied)


def _session_expiry(created_at: datetime, now: datetime) -> datetime:
    return min(created_at + ABSOLUTE_TIMEOUT, now + IDLE_TIMEOUT)


def create_session(
    db: DbSession, *, user_id: UUID, auth_time: datetime, csrf_hash_key: bytes
) -> IssuedSession:
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or user.state != "ACTIVE" or not user.beta_eligible:
        raise AuthenticationError("account is not eligible")
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    row = Session(
        user_id=user_id,
        token_hash=_digest(token),
        auth_time=min(auth_time.astimezone(UTC), now),
        last_seen_at=now,
        expires_at=now + ABSOLUTE_TIMEOUT,
        client_type="WEB",
    )
    db.add(row)
    db.flush()
    return IssuedSession(
        token=token,
        csrf_token=csrf_token(token, csrf_hash_key),
        session_id=row.id,
        user_id=user_id,
        expires_at=row.expires_at,
    )


def authenticate_session(
    db: DbSession,
    raw_token: str,
    *,
    now: datetime | None = None,
    expected_client_type: str | None = None,
) -> Session:
    moment = now or datetime.now(UTC)
    token_hash = _digest(raw_token)
    db.execute(
        text("SELECT set_config('app.auth_session_hash', :token_hash, true)"),
        {"token_hash": token_hash},
    )
    row = db.scalar(select(Session).where(Session.token_hash == token_hash).with_for_update())
    if (
        row is None
        or row.revoked_at is not None
        or (expected_client_type is not None and row.client_type != expected_client_type)
    ):
        raise AuthenticationError("session is invalid")
    db.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(row.user_id)}
    )
    user = db.scalar(select(User).where(User.id == row.user_id))
    if (
        user is None
        or user.state != "ACTIVE"
        or not user.beta_eligible
        or moment >= row.expires_at
        or moment - row.last_seen_at >= IDLE_TIMEOUT
    ):
        raise AuthenticationError("session is expired or account is unavailable")
    row.last_seen_at = moment
    row.expires_at = _session_expiry(row.created_at, moment)
    db.flush()
    return row


def revoke_session(db: DbSession, raw_token: str, *, now: datetime | None = None) -> bool:
    moment = now or datetime.now(UTC)
    token_hash = _digest(raw_token)
    db.execute(
        text("SELECT set_config('app.auth_session_hash', :token_hash, true)"),
        {"token_hash": token_hash},
    )
    owner_id = db.scalar(select(Session.user_id).where(Session.token_hash == token_hash))
    if owner_id is None:
        return False
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(owner_id)})
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Session)
            .where(Session.token_hash == token_hash, Session.revoked_at.is_(None))
            .values(revoked_at=moment)
        ),
    )
    return bool(result.rowcount)


def revoke_all_sessions(db: DbSession, user_id: UUID, *, now: datetime | None = None) -> int:
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .values(revoked_at=now or datetime.now(UTC))
        ),
    )
    return int(result.rowcount or 0)


def issue_extension_grant(
    db: DbSession,
    *,
    user_id: UUID,
    session_id: UUID,
    client_id: str,
    extension_id: str,
    pkce_challenge: str,
    state: str,
) -> tuple[str, datetime]:
    if not 43 <= len(pkce_challenge) <= 128 or not 16 <= len(state) <= 128:
        raise ValueError("invalid PKCE challenge")
    if not client_id or not extension_id:
        raise ValueError("client and extension IDs are required")
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})
    now = datetime.now(UTC)
    grant = secrets.token_urlsafe(32)
    db.add(
        ExtensionGrant(
            user_id=user_id,
            session_id=session_id,
            grant_hash=_digest(grant),
            client_id=client_id,
            extension_id=extension_id,
            pkce_challenge=pkce_challenge,
            state_hash=_digest(state),
            expires_at=now + EXTENSION_GRANT_TTL,
        )
    )
    db.flush()
    return grant, now + EXTENSION_GRANT_TTL


def consume_extension_grant(
    db: DbSession,
    *,
    grant: str,
    client_id: str,
    extension_id: str,
    state: str,
    expected_state: str,
    verifier: str,
    now: datetime | None = None,
) -> IssuedSession:
    moment = now or datetime.now(UTC)
    grant_hash = _digest(grant)
    db.execute(
        text("SELECT set_config('app.auth_grant_hash', :grant_hash, true)"),
        {"grant_hash": grant_hash},
    )
    row = db.scalar(
        select(ExtensionGrant).where(ExtensionGrant.grant_hash == grant_hash).with_for_update()
    )
    if (
        row is None
        or row.consumed_at is not None
        or row.revoked_at is not None
        or row.expires_at <= moment
        or row.client_id != client_id
        or row.extension_id != extension_id
        or not hmac.compare_digest(_digest(state), row.state_hash)
        or not hmac.compare_digest(state, expected_state)
    ):
        raise AuthenticationError("extension grant is invalid")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    if not hmac.compare_digest(challenge, row.pkce_challenge):
        raise AuthenticationError("extension PKCE verification failed")
    row.consumed_at = moment
    db.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(row.user_id)}
    )
    session = db.scalar(
        select(Session).where(Session.id == row.session_id, Session.user_id == row.user_id)
    )
    if session is None or session.revoked_at is not None or session.expires_at <= moment:
        raise AuthenticationError("source session is invalid")
    token = secrets.token_urlsafe(32)
    # Extension bearer sessions use the same revocation table and expiry bounds.
    extension_session = Session(
        user_id=row.user_id,
        token_hash=_digest(token),
        auth_time=session.auth_time,
        last_seen_at=moment,
        expires_at=_session_expiry(session.created_at, moment),
        client_type="EXTENSION",
    )
    db.add(extension_session)
    db.flush()
    return IssuedSession(
        token=token,
        csrf_token="",
        session_id=extension_session.id,
        user_id=row.user_id,
        expires_at=extension_session.expires_at,
    )
