"""Loopback-only synthetic OIDC, provider, and job-source fixtures."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings

_grants: dict[str, dict[str, str]] = {}


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _sign_token(claims: dict[str, object], secret: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _decode_token(token: str, secret: str) -> dict[str, object]:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected = _b64url(
            hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature_part):
            raise ValueError("bad signature")
        claims = json.loads(base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)))
        if not isinstance(claims, dict) or int(claims.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return claims
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid local test token") from error


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.app_env not in {"local", "test"} or not settings.local_mocks_enabled:
        raise RuntimeError(
            "Local mock services require APP_ENV=local/test and LOCAL_MOCKS_ENABLED=true"
        )
    yield


app = FastAPI(title="Local synthetic test services", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "local-synthetic-fixtures"}


@app.get("/oidc/.well-known/openid-configuration")
async def oidc_discovery() -> dict[str, object]:
    settings = get_settings()
    return {
        "issuer": settings.oidc_issuer,
        "authorization_endpoint": f"{settings.oidc_issuer}/authorize",
        "token_endpoint": f"{settings.oidc_issuer}/token",
        "userinfo_endpoint": f"{settings.oidc_issuer}/userinfo",
        "jwks_uri": f"{settings.oidc_issuer}/jwks",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    }


@app.get("/oidc/jwks")
async def oidc_jwks() -> dict[str, list[object]]:
    # The test client validates HS256 tokens with its configured client secret.
    return {"keys": []}


@app.get("/oidc/authorize")
async def oidc_authorize(request: Request) -> RedirectResponse:
    settings = get_settings()
    query = request.query_params
    redirect_uri = query.get("redirect_uri", "")
    state = query.get("state", "")
    nonce = query.get("nonce", "")
    challenge = query.get("code_challenge", "")
    if query.get("client_id") != settings.oidc_client_id:
        raise HTTPException(status_code=400, detail="Unknown local test client")
    if redirect_uri != settings.oidc_redirect_uri or not state or not nonce:
        raise HTTPException(status_code=400, detail="Invalid local authorization request")
    if (
        query.get("response_type") != "code"
        or query.get("code_challenge_method") != "S256"
        or not challenge
    ):
        raise HTTPException(status_code=400, detail="Authorization code with S256 PKCE is required")

    code = secrets.token_urlsafe(24)
    _grants[code] = {"redirect_uri": redirect_uri, "nonce": nonce, "challenge": challenge}
    return RedirectResponse(
        f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302
    )


@app.post("/oidc/token")
async def oidc_token(request: Request) -> JSONResponse:
    settings = get_settings()
    form = parse_qs((await request.body()).decode("utf-8"))
    values = {name: parts[0] for name, parts in form.items() if parts}
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Basic "):
        try:
            client_id, client_secret = base64.b64decode(authorization[6:]).decode().split(":", 1)
            values.setdefault("client_id", client_id)
            values.setdefault("client_secret", client_secret)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(
                status_code=401, detail="Invalid local test client authentication"
            ) from None

    code = values.get("code", "")
    grant = _grants.pop(code, None)
    if not grant:
        raise HTTPException(status_code=400, detail="Unknown or already used authorization code")
    if (
        values.get("grant_type") != "authorization_code"
        or values.get("redirect_uri") != grant["redirect_uri"]
        or values.get("client_id") != settings.oidc_client_id
        or values.get("client_secret") != settings.oidc_client_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid local test token request")

    verifier = values.get("code_verifier", "")
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    if not 43 <= len(verifier) <= 128 or not hmac.compare_digest(challenge, grant["challenge"]):
        raise HTTPException(status_code=400, detail="Invalid local test PKCE verifier")

    now = int(time.time())
    id_token = _sign_token(
        {
            "iss": settings.oidc_issuer,
            "sub": "local-test-user",
            "oid": "b48b1673-12f0-4ac2-a791-7432e8edc100",
            "aud": settings.oidc_client_id,
            "iat": now,
            "auth_time": now,
            "exp": now + 300,
            "nonce": grant["nonce"],
            "email": "local.user@example.test",
            "email_verified": True,
        },
        settings.oidc_client_secret or "",
    )
    access_token = _sign_token(
        {
            "iss": settings.oidc_issuer,
            "sub": "local-test-user",
            "aud": f"{settings.oidc_issuer}/userinfo",
            "scope": "openid email",
            "email": "local.user@example.test",
            "iat": now,
            "exp": now + 300,
        },
        settings.oidc_client_secret or "",
    )
    return JSONResponse(
        {
            "access_token": access_token,
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": 300,
        }
    )


@app.get("/oidc/userinfo")
async def oidc_userinfo(request: Request) -> dict[str, object]:
    settings = get_settings()
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    claims = _decode_token(authorization[7:], settings.oidc_client_secret or "")
    if claims.get("iss") != settings.oidc_issuer or claims.get("aud") != (
        f"{settings.oidc_issuer}/userinfo"
    ):
        raise HTTPException(status_code=401, detail="Invalid local test token audience")
    return {"sub": claims["sub"], "email": claims["email"], "email_verified": True}


@app.post("/provider/v1/chat/completions")
async def provider_completion() -> dict[str, object]:
    return {
        "id": "local-fixture-completion",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"fixture":true}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@app.get("/source/jobs")
async def source_jobs() -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": "local-test-job-1",
                "title": "Synthetic Software Engineer",
                "company": "Example Works",
                "location": "Remote",
                "url": "https://jobs.example.test/software-engineer",
            }
        ]
    }
