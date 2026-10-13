"""Authenticated encryption helpers for owner-scoped provider credentials."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProviderCredential
from app.security.key_encryption import KeyEncryptionProvider, LocalAesGcmKeyEncryption


class CredentialUnavailable(PermissionError):
    """A credential is missing, revoked, disabled, or not authorized for this use."""


@dataclass(frozen=True)
class CredentialSummary:
    id: UUID
    provider: str
    last4: str
    enabled: bool
    status: str
    revision: int
    allow_interactive: bool
    allow_background: bool


def _aad(owner_id: UUID, credential_id: UUID, provider: str, version: str) -> bytes:
    return f"credential:v1:{owner_id}:{credential_id}:{provider}:{version}".encode()


def _data_aad(owner_id: UUID, credential_id: UUID, provider: str) -> bytes:
    """Bind encrypted provider data to its owner, independent of KEK rotations."""
    return f"credential-data:v1:{owner_id}:{credential_id}:{provider}".encode()


def _provider_wrap_aad(owner_id: UUID, credential_id: UUID, provider: str) -> bytes:
    return f"credential-wrap:v1:{owner_id}:{credential_id}:{provider}".encode()


def _unwrap_with_provider(
    key_encryption: KeyEncryptionProvider,
    *,
    wrapped_key: bytes,
    version: str,
    context: bytes,
    legacy_context: bytes,
) -> bytes:
    try:
        return key_encryption.unwrap(wrapped_key, version, context)
    except InvalidTag:
        if not isinstance(key_encryption, LocalAesGcmKeyEncryption) or len(wrapped_key) < 29:
            raise
        return AESGCM(key_encryption.key).decrypt(
            wrapped_key[:12], wrapped_key[12:], legacy_context
        )


def _key(value: bytes | str) -> bytes:
    decoded = base64.b64decode(value, validate=True) if isinstance(value, str) else value
    if len(decoded) != 32:
        raise ValueError("KEK must contain exactly 32 bytes")
    return decoded


def store_credential(
    session: Session,
    *,
    owner_id: UUID,
    provider: str,
    api_key: str,
    kek: bytes | str | None = None,
    kek_version: str | None = None,
    key_encryption: KeyEncryptionProvider | None = None,
    allow_interactive: bool,
    allow_background: bool = False,
) -> CredentialSummary:
    """Create or replace a saved provider key; plaintext is never persisted."""
    if provider not in {"OPENROUTER", "XAI", "GEMINI"}:
        raise ValueError("unsupported provider")
    if not api_key or len(api_key) > 4096 or "\x00" in api_key:
        raise ValueError("invalid provider credential")
    if not allow_interactive and not allow_background:
        raise ValueError("at least one explicit credential purpose is required")
    row = session.scalar(
        select(ProviderCredential)
        .where(ProviderCredential.user_id == owner_id, ProviderCredential.provider == provider)
        .with_for_update()
    )
    credential_id = row.id if row else uuid4()
    data_key = AESGCM.generate_key(bit_length=256)
    wrap_aad = _aad(owner_id, credential_id, provider, kek_version or "")
    data_aad = _data_aad(owner_id, credential_id, provider)
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, api_key.encode("utf-8"), data_aad)
    if key_encryption is not None:
        wrapped_dek, resolved_kek_version = key_encryption.wrap(
            data_key, _provider_wrap_aad(owner_id, credential_id, provider)
        )
    else:
        if kek is None or not kek_version:
            raise ValueError("a KEK or key-encryption provider is required")
        wrapped_nonce = os.urandom(12)
        wrapped_dek = wrapped_nonce + AESGCM(_key(kek)).encrypt(wrapped_nonce, data_key, wrap_aad)
        resolved_kek_version = kek_version
    if row is None:
        row = ProviderCredential(
            id=credential_id,
            user_id=owner_id,
            provider=provider,
            ciphertext=ciphertext,
            nonce=nonce,
            wrapped_dek=wrapped_dek,
            kek_version=resolved_kek_version,
            key_last4=api_key[-4:].rjust(4, "•"),
            enabled=True,
            status="READY",
            revision=1,
            allow_interactive=allow_interactive,
            allow_background=allow_background,
        )
        session.add(row)
    else:
        row.ciphertext = ciphertext
        row.nonce = nonce
        row.wrapped_dek = wrapped_dek
        row.kek_version = resolved_kek_version
        row.key_last4 = api_key[-4:].rjust(4, "•")
        row.enabled = True
        row.status = "READY"
        row.revoked_at = None
        row.allow_interactive = allow_interactive
        row.allow_background = allow_background
        row.revision += 1
    session.flush()
    return summarize(row)


def summarize(row: ProviderCredential) -> CredentialSummary:
    return CredentialSummary(
        id=row.id,
        provider=row.provider,
        last4=row.key_last4,
        enabled=row.enabled,
        status=row.status,
        revision=row.revision,
        allow_interactive=row.allow_interactive,
        allow_background=row.allow_background,
    )


def unwrap_credential(
    session: Session,
    *,
    owner_id: UUID,
    credential_id: UUID,
    purpose: str,
    kek: bytes | str | None = None,
    key_encryption: KeyEncryptionProvider | None = None,
) -> str:
    """Return a key only to a trusted backend operation after owner/purpose checks."""
    if purpose not in {"interactive", "background"}:
        raise ValueError("unknown credential purpose")
    row = session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.user_id == owner_id,
            ProviderCredential.id == credential_id,
        )
    )
    if row is None or not row.enabled or row.status != "READY" or row.revoked_at is not None:
        raise CredentialUnavailable("credential is unavailable")
    allowed = row.allow_interactive if purpose == "interactive" else row.allow_background
    if not allowed:
        raise CredentialUnavailable("credential purpose was not consented")
    aad = _aad(owner_id, row.id, row.provider, row.kek_version)
    if key_encryption is not None:
        data_key = _unwrap_with_provider(
            key_encryption,
            wrapped_key=row.wrapped_dek,
            version=row.kek_version,
            context=_provider_wrap_aad(owner_id, row.id, row.provider),
            legacy_context=aad,
        )
    else:
        if kek is None:
            raise ValueError("a KEK or key-encryption provider is required")
        master = _key(kek)
        wrapped_nonce, encrypted_dek = row.wrapped_dek[:12], row.wrapped_dek[12:]
        data_key = AESGCM(master).decrypt(wrapped_nonce, encrypted_dek, aad)
    data_aad = _data_aad(owner_id, row.id, row.provider)
    try:
        cleartext = AESGCM(data_key).decrypt(row.nonce, row.ciphertext, data_aad)
    except InvalidTag as error:
        # Rows created before stable data AAD was introduced used the KEK version
        # in both ciphertexts. Keep them readable until their next rotation.
        try:
            cleartext = AESGCM(data_key).decrypt(row.nonce, row.ciphertext, aad)
        except InvalidTag:
            raise error from None
    return cleartext.decode("utf-8")


def revoke_credential(session: Session, *, owner_id: UUID, credential_id: UUID) -> bool:
    row = session.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.user_id == owner_id,
            ProviderCredential.id == credential_id,
        )
        .with_for_update()
    )
    if row is None:
        return False
    row.enabled = False
    row.status = "REVOKED"
    row.allow_interactive = False
    row.allow_background = False
    row.revoked_at = datetime.now(UTC)
    row.revision += 1
    row.ciphertext = b""
    row.wrapped_dek = b""
    session.flush()
    return True


def rotate_kek(
    session: Session,
    *,
    owner_id: UUID,
    credential_id: UUID,
    old_kek: bytes | str,
    new_kek: bytes | str,
    new_version: str,
) -> None:
    """Rewrap one owner's DEK under a new KEK without exposing the provider key."""
    row = session.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.user_id == owner_id,
            ProviderCredential.id == credential_id,
        )
        .with_for_update()
    )
    if row is None or row.status == "REVOKED":
        raise CredentialUnavailable("credential is unavailable")
    old_aad = _aad(owner_id, row.id, row.provider, row.kek_version)
    nonce, wrapped = row.wrapped_dek[:12], row.wrapped_dek[12:]
    data_key = AESGCM(_key(old_kek)).decrypt(nonce, wrapped, old_aad)
    data_aad = _data_aad(owner_id, row.id, row.provider)
    try:
        AESGCM(data_key).decrypt(row.nonce, row.ciphertext, data_aad)
    except InvalidTag:
        # Upgrade legacy version-bound ciphertext in the same locked update.
        legacy_aad = old_aad
        cleartext = AESGCM(data_key).decrypt(row.nonce, row.ciphertext, legacy_aad)
        row.nonce = os.urandom(12)
        row.ciphertext = AESGCM(data_key).encrypt(row.nonce, cleartext, data_aad)
    new_aad = _aad(owner_id, row.id, row.provider, new_version)
    new_nonce = os.urandom(12)
    row.wrapped_dek = new_nonce + AESGCM(_key(new_kek)).encrypt(new_nonce, data_key, new_aad)
    row.kek_version = new_version
    row.revision += 1
    session.flush()


def rotate_with_provider(
    session: Session,
    *,
    owner_id: UUID,
    credential_id: UUID,
    key_encryption: KeyEncryptionProvider,
) -> None:
    """Rewrap a credential DEK with the provider's current KEK version."""
    rotate_with_providers(
        session,
        owner_id=owner_id,
        credential_id=credential_id,
        old_provider=key_encryption,
        new_provider=key_encryption,
    )


def rotate_with_providers(
    session: Session,
    *,
    owner_id: UUID,
    credential_id: UUID,
    old_provider: KeyEncryptionProvider,
    new_provider: KeyEncryptionProvider,
) -> None:
    """Rewrap a credential DEK between key-encryption provider versions."""
    row = session.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.user_id == owner_id,
            ProviderCredential.id == credential_id,
        )
        .with_for_update()
    )
    if row is None or row.status == "REVOKED":
        raise CredentialUnavailable("credential is unavailable")
    old_aad = _aad(owner_id, row.id, row.provider, row.kek_version)
    wrap_aad = _provider_wrap_aad(owner_id, row.id, row.provider)
    data_key = _unwrap_with_provider(
        old_provider,
        wrapped_key=row.wrapped_dek,
        version=row.kek_version,
        context=wrap_aad,
        legacy_context=old_aad,
    )
    data_aad = _data_aad(owner_id, row.id, row.provider)
    try:
        AESGCM(data_key).decrypt(row.nonce, row.ciphertext, data_aad)
    except InvalidTag:
        legacy_cleartext = AESGCM(data_key).decrypt(row.nonce, row.ciphertext, old_aad)
        row.nonce = os.urandom(12)
        row.ciphertext = AESGCM(data_key).encrypt(row.nonce, legacy_cleartext, data_aad)
    row.wrapped_dek, row.kek_version = new_provider.wrap(data_key, wrap_aad)
    row.revision += 1
    session.flush()
