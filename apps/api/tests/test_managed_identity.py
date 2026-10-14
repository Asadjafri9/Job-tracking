"""Unit tests for the shared managed-identity IMDS helper (AZ-002)."""

from __future__ import annotations

import io
import json
from urllib.error import URLError

import pytest

from app.security import managed_identity
from app.security.managed_identity import (
    ManagedIdentityError,
    managed_identity_token,
    reset_token_cache,
)
from app.storage.blob import StorageError, _ManagedIdentityCredential


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    reset_token_cache()


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IDENTITY_ENDPOINT", "http://169.254.169.254/identity")
    monkeypatch.setenv("IDENTITY_HEADER", "secret")


def _response(payload: dict[str, object]) -> io.BytesIO:
    class FakeResponse(io.BytesIO):
        def __enter__(self) -> io.BytesIO:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    return FakeResponse(json.dumps(payload).encode())


def test_missing_endpoint_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IDENTITY_ENDPOINT", raising=False)
    monkeypatch.delenv("IDENTITY_HEADER", raising=False)
    with pytest.raises(ManagedIdentityError):
        managed_identity_token("https://vault.azure.net")


def test_token_returned_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    calls = []

    def fake_urlopen(request: object, timeout: float = 0) -> io.BytesIO:
        calls.append(request)
        return _response(
            {"access_token": "tok-1", "expires_in": 3600, "expires_on": "2000000000"}
        )

    monkeypatch.setattr(managed_identity, "urlopen", fake_urlopen)
    token, expires_on = managed_identity_token("https://storage.azure.net")
    assert token == "tok-1"
    assert expires_on == 2000000000
    token2, expires_on2 = managed_identity_token("https://storage.azure.net")
    assert (token2, expires_on2) == (token, expires_on)
    assert len(calls) == 1  # second call served from cache


def test_per_resource_cache_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(
        managed_identity,
        "urlopen",
        lambda request, timeout=0: _response(
            {"access_token": "t", "expires_in": 3600, "expires_on": "2000000000"}
        ),
    )
    managed_identity_token("https://vault.azure.net")
    managed_identity_token("https://storage.azure.net")
    assert set(managed_identity._tokens) == {
        "https://vault.azure.net",
        "https://storage.azure.net",
    }


def test_invalid_payload_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(
        managed_identity,
        "urlopen",
        lambda request, timeout=0: _response({"unexpected": True}),
    )
    with pytest.raises(ManagedIdentityError):
        managed_identity_token("https://vault.azure.net")


def test_request_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)

    def fail(request: object, timeout: float = 0) -> io.BytesIO:
        raise URLError("unreachable")

    monkeypatch.setattr(managed_identity, "urlopen", fail)
    with pytest.raises(ManagedIdentityError):
        managed_identity_token("https://vault.azure.net")


def test_credential_adapter_maps_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_token(resource: str, timeout: float = 0) -> tuple[str, int]:
        seen.append(resource)
        return "tok", 2000000000

    monkeypatch.setattr(
        "app.storage.blob.managed_identity_token", fake_token
    )
    credential = _ManagedIdentityCredential()
    access = credential.get_token("https://storage.azure.net/.default")
    assert access.token == "tok"
    assert access.expires_on == 2000000000
    assert seen == ["https://storage.azure.net"]


def test_credential_adapter_wraps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(resource: str, timeout: float = 0) -> tuple[str, int]:
        raise ManagedIdentityError("unavailable")

    monkeypatch.setattr("app.storage.blob.managed_identity_token", fail)
    with pytest.raises(StorageError):
        _ManagedIdentityCredential().get_token("https://storage.azure.net/.default")
