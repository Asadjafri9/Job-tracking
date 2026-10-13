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
    source = httpx.get(f"{oidc_issuer.removesuffix('/oidc')}/source/jobs", timeout=timeout)
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


@pytest.mark.skipif(
    os.getenv("M1_LOCAL_AUTH") != "1",
    reason="requires the isolated M1 PostgreSQL database and fake OIDC service",
)
def test_local_web_and_extension_oidc_lifecycles() -> None:
    settings = get_settings()
    if not urlparse(settings.database_url).path.lstrip("/").startswith("jobtracking_m1_"):
        pytest.skip("auth lifecycle tests may only mutate an isolated jobtracking_m1 database")
    extension_id = settings.chrome_extension_ids.split(",")[0].strip()

    def authorize(client: TestClient, **params: str) -> tuple[dict[str, str], object]:
        login = client.get("/auth/login", params=params, follow_redirects=False)
        assert login.status_code == 302
        authorization = httpx.get(login.headers["location"], follow_redirects=False, timeout=2)
        assert authorization.status_code == 302
        callback = parse_qs(urlparse(authorization.headers["location"]).query)
        response = client.get(
            "/auth/callback",
            params={"code": callback["code"][0], "state": callback["state"][0]},
            follow_redirects=False,
        )
        return callback, response

    with TestClient(api_app, base_url="https://127.0.0.1") as client:
        _, web_callback = authorize(client)
        assert web_callback.status_code == 302
        assert web_callback.headers["location"] == settings.web_app_origin
        session_cookie = web_callback.cookies.get("__Host-copilot_session")
        assert session_cookie
        session = client.get("/auth/session")
        assert session.status_code == 200
        assert session.json()["login_email"] == "local.user@example.test"
        assert "csrf_token" in session.json()

        csrf = session.json()["csrf_token"]
        browser_headers = {
            "Origin": "https://127.0.0.1",
            "X-CSRF-Token": csrf,
        }
        existing_credentials = client.get("/api/v1/provider-credentials")
        assert existing_credentials.status_code == 200
        for existing in existing_credentials.json()["credentials"]:
            deleted = client.delete(
                f"/api/v1/provider-credentials/{existing['id']}", headers=browser_headers
            )
            assert deleted.status_code == 204
        current_settings = client.get("/api/v1/provider-settings")
        assert current_settings.status_code == 200
        starting_revision = current_settings.json()["revision"]
        saved = client.put(
            "/api/v1/provider-credentials/OPENROUTER",
            json={
                "api_key": "local-openrouter-secret",
                "allow_interactive": True,
                "allow_background": False,
            },
            headers=browser_headers,
        )
        assert saved.status_code == 200
        assert saved.json()["last4"] == "cret"
        assert "local-openrouter-secret" not in saved.text
        credential_id = saved.json()["id"]

        settings_write = {
            "expected_revision": starting_revision,
            "interactive_consent": True,
            "fallback_consent": False,
            "background_consent": False,
            "routes": [
                {
                    "credential_id": credential_id,
                    "model_id": "openrouter/local-test-model",
                    "enabled": True,
                    "interactive_enabled": True,
                    "background_enabled": False,
                }
            ],
        }
        settings_response = client.put(
            "/api/v1/provider-settings",
            json=settings_write,
            headers={**browser_headers, "If-Match": f'"{starting_revision}"'},
        )
        assert settings_response.status_code == 200
        assert settings_response.json()["revision"] == starting_revision + 1
        stale_settings = client.put(
            "/api/v1/provider-settings",
            json=settings_write,
            headers={**browser_headers, "If-Match": f'"{starting_revision}"'},
        )
        assert stale_settings.status_code == 409

        revoked = client.delete(
            f"/api/v1/provider-credentials/{credential_id}", headers=browser_headers
        )
        assert revoked.status_code == 204
        assert client.get("/api/v1/provider-settings").json() == {
            "revision": starting_revision + 2,
            "interactive_consent": False,
            "fallback_consent": False,
            "background_consent": False,
            "routes": [],
        }

        rejected_logout = client.post(
            "/auth/logout", headers={"Origin": "https://127.0.0.1", "X-CSRF-Token": "wrong"}
        )
        assert rejected_logout.status_code == 403
        logout = client.post(
            "/auth/logout",
            headers={"Origin": "https://127.0.0.1", "X-CSRF-Token": csrf},
        )
        assert logout.status_code == 204
        assert client.get("/auth/session").status_code == 401

        verifier = "extension-verifier-" + ("a" * 32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        challenge_text = challenge.decode().rstrip("=")
        extension_state = "extension-state-1234567890"
        _, extension_callback = authorize(
            client,
            extension_id=extension_id,
            extension_state=extension_state,
            extension_challenge=challenge_text,
        )
        assert extension_callback.status_code == 302
        extension_redirect = urlparse(extension_callback.headers["location"])
        grant_values = parse_qs(extension_redirect.query)
        exchange_body = {
            "grant": grant_values["grant"][0],
            "state": extension_state,
            "code_verifier": verifier,
        }
        origin = f"chrome-extension://{extension_id}"
        exchange = client.post(
            "/auth/extension/exchange", json=exchange_body, headers={"Origin": origin}
        )
        assert exchange.status_code == 200
        token = exchange.json()["access_token"]
        replay = client.post(
            "/auth/extension/exchange", json=exchange_body, headers={"Origin": origin}
        )
        assert replay.status_code == 401
        extension_logout = client.post(
            "/auth/extension/logout",
            headers={"Origin": origin, "Authorization": f"Bearer {token}"},
        )
        assert extension_logout.status_code == 204
    get_settings.cache_clear()
