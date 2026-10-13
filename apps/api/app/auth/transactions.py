"""Short lived, single-use OIDC transactions with encrypted PKCE verifiers."""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthTransaction

TRANSACTION_TTL = timedelta(minutes=10)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _key(value: bytes | str) -> bytes:
    raw = base64.b64decode(value, validate=True) if isinstance(value, str) else value
    if len(raw) != 32:
        raise ValueError("auth transaction key must decode to 32 bytes")
    return raw


def create_transaction(
    db: Session,
    *,
    encryption_key: bytes | str,
    browser_binding_hash: str,
    callback_uri: str,
    client_id: str,
    extension_id: str | None = None,
    extension_pkce_challenge: str | None = None,
    extension_state: str | None = None,
    require_fresh_auth: bool = False,
) -> tuple[AuthTransaction, str, str, str]:
    state = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    nonce = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    verifier = base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    now = datetime.now(UTC)
    encryption_nonce = os.urandom(12)
    ciphertext = encryption_nonce + AESGCM(_key(encryption_key)).encrypt(
        encryption_nonce, verifier.encode(), b"oidc-pkce-verifier:v1"
    )
    row = AuthTransaction(
        state_hash=_digest(state),
        nonce_hash=_digest(nonce),
        browser_binding_hash=browser_binding_hash,
        verifier_ciphertext=ciphertext,
        callback_uri=callback_uri,
        client_id=client_id,
        extension_id=extension_id,
        extension_pkce_challenge=extension_pkce_challenge,
        extension_state=extension_state,
        require_fresh_auth=require_fresh_auth,
        pkce_challenge=challenge,
        expires_at=now + TRANSACTION_TTL,
    )
    db.add(row)
    db.flush()
    return row, state, nonce, verifier


def consume_transaction(
    db: Session,
    *,
    state: str,
    encryption_key: bytes | str,
    now: datetime | None = None,
) -> tuple[AuthTransaction, str]:
    moment = now or datetime.now(UTC)
    row = db.scalar(
        select(AuthTransaction)
        .where(AuthTransaction.state_hash == _digest(state))
        .with_for_update()
    )
    if row is None or row.consumed_at is not None or row.expires_at <= moment:
        raise ValueError("OIDC transaction is invalid or expired")
    row.consumed_at = moment
    ciphertext = row.verifier_ciphertext
    verifier = (
        AESGCM(_key(encryption_key))
        .decrypt(ciphertext[:12], ciphertext[12:], b"oidc-pkce-verifier:v1")
        .decode()
    )
    db.flush()
    return row, verifier
