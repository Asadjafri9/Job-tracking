import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.local_mocks import _grants
from app.local_mocks import app as mock_app
from app.main import app as api_app


def local_values(**overrides: str) -> dict[str, str]:
    values = {
        "APP_ENV": "local",
        "DATABASE_URL": "postgresql://copilot_runtime:runtime-local-only@127.0.0.1:55432/jobtracking",
        "MIGRATION_DATABASE_URL": "postgresql://copilot_migrator:migrator-local-only@127.0.0.1:55432/jobtracking",
        "BLOB_ENDPOINT_URL": "http://127.0.0.1:11000/devstoreaccount1",
        "OIDC_ISSUER": "http://127.0.0.1:18101/oidc",
        "OIDC_CLIENT_ID": "job-tracking-local",
        "OIDC_CLIENT_SECRET": "mock-client-secret",
        "OIDC_REDIRECT_URI": "http://127.0.0.1:18000/auth/callback",
        "LOCAL_MOCKS_ENABLED": "true",
        "CREDENTIAL_KEK_PROVIDER": "local",
        "CREDENTIAL_KEK_BASE64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    }
    values.update(overrides)
    return values


def test_app_environment_must_be_explicit() -> None:
    with pytest.raises(ValidationError, match="APP_ENV"):
        Settings.model_validate({})


def test_local_configuration_rejects_remote_mock_endpoints() -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings.model_validate(local_values(OIDC_ISSUER="https://identity.contoso.com"))


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("DATABASE_URL", "postgresql://copilot_runtime:secret@db.example.test/jobtracking"),
        (
            "MIGRATION_DATABASE_URL",
            "postgresql://copilot_migrator:secret@db.example.test/jobtracking",
        ),
        ("BLOB_ENDPOINT_URL", "https://storage.example.test/account"),
        ("OIDC_REDIRECT_URI", "https://app.example.test/auth/callback"),
    ],
)
def test_local_configuration_rejects_non_loopback_service_urls(setting: str, value: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings.model_validate(local_values(**{setting: value}))


def test_nonlocal_configuration_rejects_missing_and_local_test_settings() -> None:
    with pytest.raises(ValidationError, match="Missing production configuration"):
        Settings.model_validate({"APP_ENV": "production"})

    values = {
        "APP_ENV": "staging",
        "DATABASE_URL": "postgresql://runtime:secret@db.contoso.com:5432/jobtracking",
        "AUTH_DATABASE_URL": "postgresql://auth:secret@db.contoso.com:5432/jobtracking",
        "WORKER_DATABASE_URL": "postgresql://worker:secret@db.contoso.com:5432/jobtracking",
        "MIGRATION_DATABASE_URL": "postgresql://migrator:secret@db.contoso.com:5432/jobtracking",
        "BLOB_ENDPOINT_URL": "https://storage.contoso.com/account",
        "OIDC_ISSUER": "https://identity.contoso.com/tenant/v2.0",
        "OIDC_CLIENT_ID": "app-client",
        "OIDC_CLIENT_SECRET": "real-secret",
        "OIDC_REDIRECT_URI": "https://app.contoso.com/auth/callback",
        "WEB_APP_ORIGIN": "https://app.contoso.com",
        "BETA_ALLOWED_EMAILS": "beta@contoso.com",
        "CHROME_EXTENSION_IDS": "a" * 32,
        "APP_HASH_KEY": "hash-key-with-enough-entropy-from-secret-store",
        "AUTH_TRANSACTION_ENCRYPTION_KEY": "transaction-key-from-secret-store",
        "KEY_VAULT_CREDENTIAL_KEK_ID": "https://vault.contoso.com/keys/wrapping/abc",
        "LOCAL_MOCKS_ENABLED": "true",
        "CREDENTIAL_KEK_PROVIDER": "local",
    }
    with pytest.raises(ValidationError, match="LOCAL_MOCKS_ENABLED"):
        Settings.model_validate(values)

    production_values = {
        **values,
        "LOCAL_MOCKS_ENABLED": "false",
        "CREDENTIAL_KEK_PROVIDER": "key_vault",
    }
    production_values.pop("OIDC_CLIENT_ID")
    production_values.pop("OIDC_CLIENT_SECRET")
    production_values.pop("CREDENTIAL_KEK_BASE64", None)
    with pytest.raises(ValidationError, match="Missing production configuration") as error:
        Settings.model_validate(production_values)
    assert "OIDC_CLIENT_ID" in str(error.value)
    assert "OIDC_CLIENT_SECRET" in str(error.value)

    valid_nonlocal_values = {
        **values,
        "LOCAL_MOCKS_ENABLED": "false",
        "CREDENTIAL_KEK_PROVIDER": "key_vault",
    }
    Settings.model_validate(valid_nonlocal_values)

    fake_identity_values = {
        **valid_nonlocal_values,
        "OIDC_ISSUER": "https://fake-identity.contoso.com/tenant/v2.0",
    }
    with pytest.raises(ValidationError, match="Missing production configuration"):
        Settings.model_validate(fake_identity_values)


def test_local_oidc_fixture_enforces_state_and_pkce(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in local_values().items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    _grants.clear()

    verifier = "a" * 43
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    with TestClient(mock_app) as client:
        response = client.get(
            "/oidc/authorize",
            params={
                "client_id": "job-tracking-local",
                "redirect_uri": "http://127.0.0.1:18000/auth/callback",
                "response_type": "code",
                "scope": "openid email",
                "state": "state-123",
                "nonce": "nonce-123",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        redirect = urlparse(response.headers["location"])
        callback = parse_qs(redirect.query)
        assert callback["state"] == ["state-123"]

        token_response = client.post(
            "/oidc/token",
            data={
                "grant_type": "authorization_code",
                "code": callback["code"][0],
                "redirect_uri": "http://127.0.0.1:18000/auth/callback",
                "client_id": "job-tracking-local",
                "client_secret": "mock-client-secret",
                "code_verifier": verifier,
            },
        )
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]
        user_response = client.get("/oidc/userinfo", headers={"Authorization": f"Bearer {token}"})
        assert user_response.json()["sub"] == "local-test-user"

        replay = client.post(
            "/oidc/token",
            data={
                "grant_type": "authorization_code",
                "code": callback["code"][0],
                "redirect_uri": "http://127.0.0.1:18000/auth/callback",
                "client_id": "job-tracking-local",
                "client_secret": "mock-client-secret",
                "code_verifier": verifier,
            },
        )
        assert replay.status_code == 400

    get_settings.cache_clear()


def test_fake_provider_and_source_return_synthetic_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in local_values().items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    with TestClient(mock_app) as client:
        provider = client.post("/provider/v1/chat/completions", json={"messages": []})
        source = client.get("/source/jobs")
    assert provider.json()["id"] == "local-fixture-completion"
    assert source.json()["jobs"][0]["id"] == "local-test-job-1"
    get_settings.cache_clear()


def test_local_mock_service_refuses_production_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://runtime:secret@db.contoso.com:5432/jobtracking",
        "AUTH_DATABASE_URL": "postgresql://auth:secret@db.contoso.com:5432/jobtracking",
        "WORKER_DATABASE_URL": "postgresql://worker:secret@db.contoso.com:5432/jobtracking",
        "MIGRATION_DATABASE_URL": "postgresql://migrator:secret@db.contoso.com:5432/jobtracking",
        "BLOB_ENDPOINT_URL": "https://storage.contoso.com/account",
        "OIDC_ISSUER": "https://identity.contoso.com/tenant/v2.0",
        "OIDC_CLIENT_ID": "app-client",
        "OIDC_CLIENT_SECRET": "real-secret",
        "OIDC_REDIRECT_URI": "https://app.contoso.com/auth/callback",
        "WEB_APP_ORIGIN": "https://app.contoso.com",
        "BETA_ALLOWED_EMAILS": "beta@contoso.com",
        "CHROME_EXTENSION_IDS": "a" * 32,
        "APP_HASH_KEY": "hash-key-with-enough-entropy-from-secret-store",
        "AUTH_TRANSACTION_ENCRYPTION_KEY": "transaction-key-from-secret-store",
        "KEY_VAULT_CREDENTIAL_KEK_ID": "https://vault.contoso.com/keys/wrapping/abc",
        "LOCAL_MOCKS_ENABLED": "false",
        "CREDENTIAL_KEK_PROVIDER": "key_vault",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("CREDENTIAL_KEK_BASE64", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Local mock services require"):
        with TestClient(mock_app):
            pass
    get_settings.cache_clear()


def test_local_readiness_authenticates_services_without_claiming_schema_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in local_values().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("app.main._can_authenticate_postgres", lambda _: True)
    monkeypatch.setattr("app.main._can_authorize_local_blob", lambda _: True)
    get_settings.cache_clear()
    with TestClient(api_app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["dependencies"] == {
        "postgresql_authentication": "ok",
        "blob_storage_authorization": "ok",
    }
    assert "database_schema_compatibility" in response.json()["unverified"]
    get_settings.cache_clear()


def test_local_readiness_stays_closed_when_a_service_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in local_values().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("app.main._can_authenticate_postgres", lambda _: True)
    monkeypatch.setattr("app.main._can_authorize_local_blob", lambda _: False)
    get_settings.cache_clear()
    with TestClient(api_app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["blob_storage_authorization"] == "unavailable"
    get_settings.cache_clear()
