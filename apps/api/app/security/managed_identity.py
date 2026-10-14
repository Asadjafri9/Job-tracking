"""App Service managed-identity token acquisition via the IMDS endpoint.

Used by the Key Vault KEK adapter and production blob storage so the same
system-assigned identity covers both role assignments from the deployment
plan. Tokens are cached per resource until 60 seconds before expiry; no
token material is written to disk or logged.
"""

from __future__ import annotations

import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ManagedIdentityError(RuntimeError):
    """The managed-identity endpoint did not return a usable token."""


_lock = threading.Lock()
# resource -> (token, monotonic_expiry, expires_on_epoch)
_tokens: dict[str, tuple[str, float, int]] = {}


def managed_identity_token(resource: str, timeout: float = 5.0) -> tuple[str, int]:
    """Return ``(access_token, expires_on_epoch_seconds)`` for *resource*."""
    now = time.monotonic()
    with _lock:
        cached = _tokens.get(resource)
        if cached and now < cached[1] - 60:
            return cached[0], cached[2]
    endpoint = os.environ.get("IDENTITY_ENDPOINT")
    secret = os.environ.get("IDENTITY_HEADER")
    if not endpoint or not secret:
        raise ManagedIdentityError("App Service managed identity is unavailable")
    query = urlencode({"resource": resource, "api-version": "2019-08-01"})
    request = Request(
        f"{endpoint}?{query}",
        headers={"X-IDENTITY-HEADER": secret, "Metadata": "true"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(16_384))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        raise ManagedIdentityError("Managed identity token request failed") from error
    if not isinstance(payload, dict):
        raise ManagedIdentityError("Managed identity returned an invalid response")
    token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not isinstance(token, str) or not isinstance(expires_in, (str, int, float)):
        raise ManagedIdentityError("Managed identity returned an invalid access token")
    expires_on = int(payload.get("expires_on") or time.time() + float(expires_in))
    with _lock:
        _tokens[resource] = (token, now + float(expires_in), expires_on)
    return token, expires_on


def reset_token_cache() -> None:
    """Test hook: drop all cached tokens."""
    with _lock:
        _tokens.clear()
