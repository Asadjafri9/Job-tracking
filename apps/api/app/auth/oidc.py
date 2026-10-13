"""OIDC discovery, authorization-code exchange and ID-token validation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from authlib.integrations.requests_client import OAuth2Session  # type: ignore[import-untyped]
from joserfc import jwk, jwt
from joserfc.errors import JoseError


class OIDCError(ValueError):
    """OIDC response failed issuer, token, or claim validation."""


class _NoRedirect(HTTPRedirectHandler):
    """Never forward an authorization code or client secret to a redirected endpoint."""

    def redirect_request(
        self, request: Request, file: Any, code: int, message: str, headers: Any, new_url: str
    ) -> None:
        return None


class _NoRedirectOAuth2Session(OAuth2Session):
    """Authlib OAuth client that never forwards a token request to a redirect target."""

    def request(
        self,
        method: str,
        url: str,
        *,
        withhold_token: bool = False,
        auth: Any = None,
        **kwargs: Any,
    ):  # type: ignore[no-untyped-def]
        kwargs["allow_redirects"] = False
        return super().request(method, url, withhold_token=withhold_token, auth=auth, **kwargs)


def _json_request(
    url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    request = Request(url, data=data, headers=headers or {})
    try:
        with build_opener(_NoRedirect).open(request, timeout=8) as response:
            value = json.loads(response.read(1_048_577))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise OIDCError("identity provider request failed") from error
    if not isinstance(value, dict):
        raise OIDCError("identity provider returned an invalid response")
    return value


def discover(issuer: str) -> dict[str, Any]:
    metadata = _json_request(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
    if metadata.get("issuer") != issuer:
        raise OIDCError("discovered issuer does not match configured issuer")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        endpoint = metadata.get(name)
        if not isinstance(endpoint, str):
            raise OIDCError("identity metadata contains an untrusted endpoint")
        parsed = urlparse(endpoint)
        local_host = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            parsed.scheme not in {"https", "http"}
            or (parsed.scheme != "https" and not local_host)
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise OIDCError("identity metadata contains an untrusted endpoint")
    return metadata


def authorization_url(
    *,
    metadata: dict[str, Any],
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    verifier: str,
    fresh: bool = False,
) -> str:
    client = OAuth2Session(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope="openid email profile",
        code_challenge_method="S256",
    )
    parameters: dict[str, str] = {"nonce": nonce}
    if fresh:
        parameters["prompt"] = "login"
        parameters["max_age"] = "0"
    url, _ = client.create_authorization_url(
        str(metadata["authorization_endpoint"]),
        state=state,
        code_verifier=verifier,
        **parameters,
    )
    return url


def exchange_code(
    *,
    metadata: dict[str, Any],
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    verifier: str,
) -> str:
    client = _NoRedirectOAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint_auth_method="client_secret_post",
        redirect_uri=redirect_uri,
        default_timeout=8,
    )
    try:
        token = client.fetch_token(
            str(metadata["token_endpoint"]),
            grant_type="authorization_code",
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=verifier,
        )
    except Exception as error:
        raise OIDCError("identity provider token exchange failed") from error
    finally:
        client.close()
    id_token = token.get("id_token")
    if not isinstance(id_token, str):
        raise OIDCError("identity provider did not return an ID token")
    return id_token


def verify_id_token(
    token: str,
    *,
    metadata: dict[str, Any],
    client_id: str,
    client_secret: str,
    expected_nonce_hash: str,
    local_test: bool,
) -> dict[str, Any]:
    try:
        header_part, _, _ = token.split(".")
        header = json.loads(base64.urlsafe_b64decode(header_part + "=" * (-len(header_part) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise OIDCError("malformed ID token") from error
    if not isinstance(header, dict):
        raise OIDCError("malformed ID token")
    algorithm = header.get("alg")
    try:
        if algorithm == "RS256":
            jwks = _json_request(str(metadata["jwks_uri"]))
            keys = jwks.get("keys")
            kid = header.get("kid")
            if not isinstance(keys, list):
                raise OIDCError("identity provider returned malformed signing keys")
            signing_key = next(
                key
                for key in keys
                if isinstance(key, dict)
                and key.get("kid") == kid
                and key.get("kty") == "RSA"
                and key.get("use") in (None, "sig")
                and key.get("alg") in (None, "RS256")
            )
            public_key = jwk.import_key(signing_key)
            if len(str(signing_key.get("n", ""))) < 342:
                raise OIDCError("ID token signing key is too weak")
            parsed = jwt.decode(token, public_key, algorithms=["RS256"])
        elif algorithm == "HS256" and local_test:
            parsed = jwt.decode(
                token,
                jwk.import_key(client_secret, key_type="oct"),
                algorithms=["HS256"],
            )
        else:
            raise OIDCError("ID token algorithm is not allowed")
        claims = parsed.claims
    except OIDCError:
        raise
    except (JoseError, KeyError, StopIteration, TypeError, ValueError) as error:
        raise OIDCError("ID token signature is invalid") from error

    now = int(time.time())
    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience
    expiration = claims.get("exp")
    issued_at = claims.get("iat")
    not_before = claims.get("nbf")
    auth_time = claims.get("auth_time")
    if (
        claims.get("iss") != metadata.get("issuer")
        or not isinstance(audiences, list)
        or not audiences
        or any(not isinstance(value, str) for value in audiences)
        or client_id not in audiences
        or ("azp" in claims and claims.get("azp") != client_id)
        or (len(audiences) > 1 and claims.get("azp") != client_id)
        or not isinstance(expiration, (int, float))
        or isinstance(expiration, bool)
        or expiration <= now
        or not isinstance(issued_at, (int, float))
        or isinstance(issued_at, bool)
        or issued_at < now - 3600
        or issued_at > now + 60
        or expiration <= issued_at
        or expiration - issued_at > 3600
        or (
            "nbf" in claims
            and (
                not isinstance(not_before, (int, float))
                or isinstance(not_before, bool)
                or not_before > now + 60
            )
        )
        or not isinstance(claims.get("nonce"), str)
        or not hmac.compare_digest(
            hashlib.sha256(claims["nonce"].encode()).hexdigest(), expected_nonce_hash
        )
        or not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or (
            "auth_time" in claims
            and (
                not isinstance(auth_time, (int, float))
                or isinstance(auth_time, bool)
                or auth_time > now + 60
            )
        )
    ):
        raise OIDCError("ID token claims are invalid")
    if claims.get("email_verified") is not True or not isinstance(claims.get("email"), str):
        raise OIDCError("identity provider did not verify the login email")
    return claims
