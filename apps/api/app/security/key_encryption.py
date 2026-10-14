"""KEK providers for wrapping credential data-encryption keys."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.security.managed_identity import ManagedIdentityError, managed_identity_token


class KeyEncryptionError(RuntimeError):
    """A configured key-encryption service could not wrap or unwrap a DEK."""


class KeyEncryptionProvider(Protocol):
    def wrap(self, data_key: bytes, context: bytes) -> tuple[bytes, str]: ...

    def unwrap(self, wrapped_key: bytes, version: str, context: bytes) -> bytes: ...


@dataclass(frozen=True)
class LocalAesGcmKeyEncryption:
    key: bytes
    version: str

    def wrap(self, data_key: bytes, context: bytes) -> tuple[bytes, str]:
        nonce = os.urandom(12)
        aad = context + b":" + self.version.encode()
        return nonce + AESGCM(self.key).encrypt(nonce, data_key, aad), self.version

    def unwrap(self, wrapped_key: bytes, version: str, context: bytes) -> bytes:
        if version != self.version or len(wrapped_key) < 29:
            raise KeyEncryptionError("The local KEK version does not match the credential")
        aad = context + b":" + version.encode()
        return AESGCM(self.key).decrypt(wrapped_key[:12], wrapped_key[12:], aad)


class KeyVaultKeyEncryption:
    """Wrap DEKs with a versioned Azure Key Vault RSA key via its REST API.

    Authentication uses the App Service managed-identity endpoint. No key
    material or access token is written to disk or logged.
    """

    def __init__(self, key_id: str, *, timeout: float = 5.0) -> None:
        parsed = urlsplit(key_id)
        path_parts = parsed.path.strip("/").split("/")
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or len(path_parts) != 3
            or path_parts[0] != "keys"
            or not path_parts[1]
            or not path_parts[2]
        ):
            raise ValueError("Key Vault credential KEK ID must be a versioned HTTPS key URI")
        self.key_id = key_id.rstrip("/")
        self.timeout = timeout

    def wrap(self, data_key: bytes, context: bytes) -> tuple[bytes, str]:
        del context  # Key Vault's wrapKey operation does not accept additional AAD.
        result = self._request(self.key_id, "wrapkey", data_key)
        wrapped = _decode_b64url(result.get("value"))
        version = result.get("kid")
        if not version or not isinstance(version, str) or not wrapped:
            raise KeyEncryptionError("Key Vault returned an invalid wrapped key")
        return wrapped, version

    def unwrap(self, wrapped_key: bytes, version: str, context: bytes) -> bytes:
        del context
        result = self._request(version, "unwrapkey", wrapped_key)
        data_key = _decode_b64url(result.get("value"))
        if len(data_key) != 32:
            raise KeyEncryptionError("Key Vault returned an invalid data key")
        return data_key

    def _request(self, key_id: str, operation: str, value: bytes) -> dict[str, object]:
        url = f"{key_id.rstrip('/')}/{operation}?api-version=7.4"
        body = json.dumps(
            {"alg": "RSA-OAEP-256", "value": _encode_b64url(value)},
            separators=(",", ":"),
        ).encode()
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(16_384))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            raise KeyEncryptionError("Key Vault key operation failed") from error
        if not isinstance(payload, dict):
            raise KeyEncryptionError("Key Vault returned an invalid response")
        return payload

    def _access_token(self) -> str:
        try:
            token, _ = managed_identity_token("https://vault.azure.net", self.timeout)
        except ManagedIdentityError as error:
            raise KeyEncryptionError(str(error)) from error
        return token


def _encode_b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: object) -> bytes:
    if not isinstance(value, str):
        return b""
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as error:
        raise KeyEncryptionError("Key Vault returned malformed base64url data") from error
