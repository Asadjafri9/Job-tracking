"""Focused tests for local OIDC validation and request concurrency primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.auth.oidc import OIDCError, authorization_url, discover, verify_id_token
from app.auth.sessions import ABSOLUTE_TIMEOUT, IDLE_TIMEOUT, _session_expiry
from app.db.idempotency import IdempotencyConflict, fingerprint, require_revision
from app.security.credentials import (
    rotate_kek,
    rotate_with_providers,
    store_credential,
    unwrap_credential,
)
from app.security.key_encryption import KeyVaultKeyEncryption, LocalAesGcmKeyEncryption

LOCAL_SECRET = "local-test-secret-at-least-112-bits"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _token(claims: dict[str, object], secret: str) -> str:
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    message = f"{header}.{payload}"
    signature = _b64(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest())
    return f"{message}.{signature}"


def _claims(nonce: str) -> dict[str, object]:
    now = int(time.time())
    return {
        "iss": "http://127.0.0.1:18101/oidc",
        "sub": "local-subject",
        "oid": "b48b1673-12f0-4ac2-a791-7432e8edc100",
        "aud": "local-client",
        "iat": now,
        "exp": now + 120,
        "nonce": nonce,
        "email": "local.user@example.test",
        "email_verified": True,
    }


def _verify(token: str, nonce: str, *, local: bool = True) -> dict[str, object]:
    return verify_id_token(
        token,
        metadata={"issuer": "http://127.0.0.1:18101/oidc", "jwks_uri": ""},
        client_id="local-client",
        client_secret=LOCAL_SECRET,
        expected_nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
        local_test=local,
    )


def test_local_oidc_validates_signature_nonce_and_claims() -> None:
    nonce = "random-oidc-nonce"
    claims = _verify(_token(_claims(nonce), LOCAL_SECRET), nonce)
    assert claims["sub"] == "local-subject"


def test_local_oidc_rejects_bad_nonce_and_signature() -> None:
    nonce = "random-oidc-nonce"
    token = _token(_claims(nonce), LOCAL_SECRET)
    with pytest.raises(OIDCError):
        _verify(token, "different-nonce")
    with pytest.raises(OIDCError):
        _verify(_token(_claims(nonce), "wrong-secret"), nonce)


def test_local_oidc_rejects_wrong_authorized_party_and_overlong_tokens() -> None:
    nonce = "random-oidc-nonce"
    wrong_party = _claims(nonce) | {"azp": "another-client"}
    with pytest.raises(OIDCError):
        _verify(_token(wrong_party, LOCAL_SECRET), nonce)
    overlong = _claims(nonce) | {"exp": int(time.time()) + 7200}
    with pytest.raises(OIDCError):
        _verify(_token(overlong, LOCAL_SECRET), nonce)


def test_local_hmac_tokens_are_never_accepted_outside_test() -> None:
    nonce = "random-oidc-nonce"
    with pytest.raises(OIDCError):
        _verify(_token(_claims(nonce), LOCAL_SECRET), nonce, local=False)


def test_authlib_builds_s256_pkce_authorization_request() -> None:
    verifier = "v" * 64
    url = authorization_url(
        metadata={"authorization_endpoint": "https://identity.example.test/authorize"},
        client_id="client-id",
        redirect_uri="https://app.example.test/auth/callback",
        state="random-state",
        nonce="random-nonce",
        verifier=verifier,
        fresh=True,
    )
    parameters = parse_qs(urlparse(url).query)
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["code_challenge"] == [_b64(hashlib.sha256(verifier.encode()).digest())]
    assert parameters["state"] == ["random-state"]
    assert parameters["nonce"] == ["random-nonce"]
    assert parameters["prompt"] == ["login"]
    assert parameters["max_age"] == ["0"]


def test_production_oidc_verifies_rs256_jwks_signature_and_authorized_party() -> None:
    nonce = "production-nonce"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    header = _b64(json.dumps({"alg": "RS256", "kid": "test-kid"}).encode())
    claims = _claims(nonce) | {"aud": ["local-client", "another-client"], "azp": "local-client"}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    signature = private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    token = f"{signing_input}.{_b64(signature)}"
    jwk = {
        "kty": "RSA",
        "kid": "test-kid",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")),
    }
    metadata = {"issuer": claims["iss"], "jwks_uri": "https://identity.example.test/jwks"}
    with patch("app.auth.oidc._json_request", return_value={"keys": [jwk]}):
        verified = verify_id_token(
            token,
            metadata=metadata,
            client_id="local-client",
            client_secret="unused-outside-local-test",
            expected_nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
            local_test=False,
        )
    assert verified["sub"] == "local-subject"

    invalid_claims = claims | {"azp": "another-client"}
    invalid_payload = _b64(json.dumps(invalid_claims, separators=(",", ":")).encode())
    invalid_input = f"{header}.{invalid_payload}"
    invalid_signature = private_key.sign(
        invalid_input.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    invalid_token = f"{invalid_input}.{_b64(invalid_signature)}"
    with patch("app.auth.oidc._json_request", return_value={"keys": [jwk]}):
        with pytest.raises(OIDCError, match="claims"):
            verify_id_token(
                invalid_token,
                metadata=metadata,
                client_id="local-client",
                client_secret="unused-outside-local-test",
                expected_nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
                local_test=False,
            )


def test_oidc_discovery_rejects_http_endpoints_that_only_prefix_match_loopback() -> None:
    metadata = {
        "issuer": "http://127.0.0.1:18101/oidc",
        "authorization_endpoint": "http://localhost.attacker.test/authorize",
        "token_endpoint": "http://127.0.0.1:18101/token",
        "jwks_uri": "http://127.0.0.1:18101/jwks",
    }
    with patch("app.auth.oidc._json_request", return_value=metadata):
        with pytest.raises(OIDCError, match="untrusted endpoint"):
            discover("http://127.0.0.1:18101/oidc")


def test_idempotency_fingerprint_is_stable_and_secret_keyed() -> None:
    payload = {"job": "designer", "location": "remote"}
    first = fingerprint(b"key-a", payload)
    assert first == fingerprint(b"key-a", {"location": "remote", "job": "designer"})
    assert first != fingerprint(b"key-b", payload)


def test_optimistic_revision_check_reports_stale_writes() -> None:
    require_revision(4, 4)
    with pytest.raises(IdempotencyConflict):
        require_revision(5, 4)


def test_session_expiry_uses_application_issue_time_not_provider_auth_time() -> None:
    issued_at = datetime(2026, 10, 13, 12, tzinfo=UTC)
    current = issued_at + timedelta(minutes=30)
    assert _session_expiry(issued_at, current) == issued_at + timedelta(minutes=90)
    assert _session_expiry(issued_at, issued_at + timedelta(hours=11)) == (
        issued_at + ABSOLUTE_TIMEOUT
    )
    assert IDLE_TIMEOUT == timedelta(minutes=60)


class _CredentialSession:
    def __init__(self) -> None:
        self.row = None

    def scalar(self, _statement):
        return self.row

    def add(self, row) -> None:
        self.row = row

    def flush(self) -> None:
        pass


def test_kek_rotation_keeps_provider_key_decryptable() -> None:
    session = _CredentialSession()
    owner_id = uuid4()
    old_kek = b"a" * 32
    new_kek = b"b" * 32
    store_credential(
        session,
        owner_id=owner_id,
        provider="OPENROUTER",
        api_key="provider-secret-1234",
        kek=old_kek,
        kek_version="old-v1",
        allow_interactive=True,
    )
    row = session.row

    rotate_kek(
        session,
        owner_id=owner_id,
        credential_id=row.id,
        old_kek=old_kek,
        new_kek=new_kek,
        new_version="new-v2",
    )

    assert (
        unwrap_credential(
            session,
            owner_id=owner_id,
            credential_id=row.id,
            purpose="interactive",
            kek=new_kek,
        )
        == "provider-secret-1234"
    )


def test_key_encryption_provider_round_trips_saved_credential() -> None:
    session = _CredentialSession()
    owner_id = uuid4()
    provider = LocalAesGcmKeyEncryption(b"c" * 32, "local-v2")
    store_credential(
        session,
        owner_id=owner_id,
        provider="XAI",
        api_key="xai-secret-1234",
        key_encryption=provider,
        allow_interactive=True,
    )

    assert (
        unwrap_credential(
            session,
            owner_id=owner_id,
            credential_id=session.row.id,
            purpose="interactive",
            key_encryption=provider,
        )
        == "xai-secret-1234"
    )


def test_local_provider_can_read_credentials_from_the_previous_wrapper_format() -> None:
    session = _CredentialSession()
    owner_id = uuid4()
    kek = b"e" * 32
    store_credential(
        session,
        owner_id=owner_id,
        provider="GEMINI",
        api_key="gemini-secret-1234",
        kek=kek,
        kek_version="local-test-v1",
        allow_interactive=True,
    )

    assert (
        unwrap_credential(
            session,
            owner_id=owner_id,
            credential_id=session.row.id,
            purpose="interactive",
            key_encryption=LocalAesGcmKeyEncryption(kek, "local-test-v1"),
        )
        == "gemini-secret-1234"
    )


def test_provider_rotation_rewraps_dek_with_new_local_key_version() -> None:
    session = _CredentialSession()
    owner_id = uuid4()
    old_provider = LocalAesGcmKeyEncryption(b"f" * 32, "old-local-v1")
    new_provider = LocalAesGcmKeyEncryption(b"g" * 32, "new-local-v2")
    store_credential(
        session,
        owner_id=owner_id,
        provider="OPENROUTER",
        api_key="openrouter-secret",
        key_encryption=old_provider,
        allow_interactive=True,
    )
    credential_id = session.row.id

    rotate_with_providers(
        session,
        owner_id=owner_id,
        credential_id=credential_id,
        old_provider=old_provider,
        new_provider=new_provider,
    )

    assert session.row.kek_version == "new-local-v2"
    assert (
        unwrap_credential(
            session,
            owner_id=owner_id,
            credential_id=credential_id,
            purpose="interactive",
            key_encryption=new_provider,
        )
        == "openrouter-secret"
    )


def test_key_vault_wrap_and_unwrap_use_versioned_key_uri() -> None:
    class _Response:
        def __init__(self, payload: dict[str, str]) -> None:
            self.payload = json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def read(self, _limit: int) -> bytes:
            return self.payload

    wrapped = _b64(b"wrapped-dek")
    key_id = "https://vault.example/keys/credential-kek/version-7"
    vault = KeyVaultKeyEncryption(key_id)
    request_urls: list[str] = []

    def response_for(request, timeout: float):
        assert timeout == 5.0
        request_urls.append(request.full_url)
        if "/wrapkey?" in request.full_url:
            return _Response({"value": wrapped, "kid": key_id})
        return _Response({"value": _b64(b"d" * 32)})

    with (
        patch.object(vault, "_access_token", return_value="test-token"),
        patch("app.security.key_encryption.urlopen", side_effect=response_for),
    ):
        ciphertext, version = vault.wrap(b"d" * 32, b"credential-context")
        cleartext = vault.unwrap(ciphertext, version, b"credential-context")

    assert ciphertext == b"wrapped-dek"
    assert version == key_id
    assert cleartext == b"d" * 32
    assert "/wrapkey?api-version=7.4" in request_urls[0]
    assert f"{key_id}/unwrapkey?api-version=7.4" in request_urls[1]
