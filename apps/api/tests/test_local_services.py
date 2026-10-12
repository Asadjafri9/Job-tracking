"""Opt-in checks against the loopback-only Compose stack and fake HTTP services."""

import base64
import hashlib
import os
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app as api_app


@pytest.mark.skipif(
    os.getenv("SET002_LOCAL_SERVICES") != "1",
    reason="requires the loopback-only PostgreSQL/Azurite/fake-service stack",
)
def test_local_compose_roles_storage_health_and_synthetic_services() -> None:
    database_url = os.environ["DATABASE_URL"]
    migration_database_url = os.environ["MIGRATION_DATABASE_URL"]
    oidc_issuer = os.environ["OIDC_ISSUER"]

    with psycopg.connect(database_url, connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
            assert cursor.fetchone() == ("copilot_runtime", False, False, False, False)
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)

    with psycopg.connect(migration_database_url, connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            assert cursor.fetchone() == ("copilot_migrator",)
            cursor.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()"
            )
            assert cursor.fetchone() == ("copilot_migrator",)

    with TestClient(api_app) as client:
        readiness = client.get("/health/ready")
    assert readiness.status_code == 200
    assert readiness.json()["dependencies"] == {
        "postgresql_authentication": "ok",
        "blob_storage_authorization": "ok",
    }
    assert readiness.json()["unverified"] == ["database_schema_compatibility"]

    timeout = httpx.Timeout(2)
    discovery = httpx.get(f"{oidc_issuer}/.well-known/openid-configuration", timeout=timeout)
    provider = httpx.post(
        f"{oidc_issuer.removesuffix('/oidc')}/provider/v1/chat/completions",
        json={"messages": []},
        timeout=timeout,
    )
    source = httpx.get(
        f"{oidc_issuer.removesuffix('/oidc')}/source/jobs", timeout=timeout
    )
    assert discovery.status_code == 200
    assert discovery.json()["issuer"] == oidc_issuer
    assert provider.status_code == 200
    assert provider.json()["id"] == "local-fixture-completion"
    assert source.status_code == 200
    assert source.json()["jobs"][0]["id"] == "local-test-job-1"

    verifier = "b" * 43
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    challenge_text = challenge.decode().rstrip("=")
    authorization = httpx.get(
        f"{oidc_issuer}/authorize",
        params={
            "client_id": os.environ["OIDC_CLIENT_ID"],
            "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
            "response_type": "code",
            "scope": "openid email",
            "state": "set002-local-state",
            "nonce": "set002-local-nonce",
            "code_challenge": challenge_text,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
        timeout=timeout,
    )
    assert authorization.status_code == 302
    callback = parse_qs(urlparse(authorization.headers["location"]).query)
    assert callback["state"] == ["set002-local-state"]

    token_response = httpx.post(
        f"{oidc_issuer}/token",
        data={
            "grant_type": "authorization_code",
            "code": callback["code"][0],
            "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
            "client_id": os.environ["OIDC_CLIENT_ID"],
            "client_secret": os.environ["OIDC_CLIENT_SECRET"],
            "code_verifier": verifier,
        },
        timeout=timeout,
    )
    assert token_response.status_code == 200
    userinfo = httpx.get(
        f"{oidc_issuer}/userinfo",
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
        timeout=timeout,
    )
    assert userinfo.status_code == 200
    assert userinfo.json()["sub"] == "local-test-user"

    get_settings.cache_clear()
