"""Environment configuration with production guardrails and local-only test adapters."""

import base64
import binascii
import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

LOCAL_TEST_KEK = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    app_env: Literal["local", "test", "staging", "production"] = Field(alias="APP_ENV")
    database_url: str = Field(
        default="postgresql://copilot_runtime:runtime-local-only@127.0.0.1:55432/jobtracking",
        alias="DATABASE_URL",
    )
    auth_database_url: str = Field(
        default="postgresql://copilot_auth:auth-local-only@127.0.0.1:55432/jobtracking",
        alias="AUTH_DATABASE_URL",
    )
    worker_database_url: str = Field(
        default="postgresql://copilot_worker:worker-local-only@127.0.0.1:55432/jobtracking",
        alias="WORKER_DATABASE_URL",
    )
    scheduler_database_url: str = Field(
        default=("postgresql://copilot_scheduler:scheduler-local-only@127.0.0.1:55432/jobtracking"),
        alias="SCHEDULER_DATABASE_URL",
    )
    migration_database_url: str = Field(
        default="postgresql://copilot_migrator:migrator-local-only@127.0.0.1:55432/jobtracking",
        alias="MIGRATION_DATABASE_URL",
    )
    blob_endpoint_url: str = Field(
        default="http://127.0.0.1:11000/devstoreaccount1", alias="BLOB_ENDPOINT_URL"
    )
    oidc_issuer: str | None = Field(default="http://127.0.0.1:18101/oidc", alias="OIDC_ISSUER")
    oidc_client_id: str | None = Field(default="job-tracking-local", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default="mock-client-secret", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str | None = Field(
        default="http://127.0.0.1:18000/auth/callback", alias="OIDC_REDIRECT_URI"
    )
    web_app_origin: str = Field(default="http://127.0.0.1:5173", alias="WEB_APP_ORIGIN")
    beta_allowed_emails: str = Field(default="local.user@example.test", alias="BETA_ALLOWED_EMAILS")
    chrome_extension_ids: str = Field(
        default="digpnmcecpkodggeieillcjpfgpokgnk", alias="CHROME_EXTENSION_IDS"
    )
    local_mocks_enabled: bool = Field(default=True, alias="LOCAL_MOCKS_ENABLED")
    credential_kek_provider: Literal["local", "key_vault"] = Field(
        default="local", alias="CREDENTIAL_KEK_PROVIDER"
    )
    credential_kek_base64: str | None = Field(default=None, alias="CREDENTIAL_KEK_BASE64")
    app_hash_key: str | None = Field(default=None, alias="APP_HASH_KEY")
    auth_transaction_encryption_key: str | None = Field(
        default=None, alias="AUTH_TRANSACTION_ENCRYPTION_KEY"
    )
    key_vault_credential_kek_id: str | None = Field(
        default=None, alias="KEY_VAULT_CREDENTIAL_KEK_ID"
    )
    web_dist_dir: str | None = Field(default=None, alias="WEB_DIST_DIR")

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        web_origin = urlparse(self.web_app_origin)
        if (
            web_origin.scheme not in {"http", "https"}
            or not web_origin.hostname
            or web_origin.username is not None
            or web_origin.password is not None
            or web_origin.path not in {"", "/"}
            or web_origin.query
            or web_origin.fragment
        ):
            raise ValueError(
                "WEB_APP_ORIGIN must be an HTTP(S) origin without a path or credentials"
            )
        if self.app_env in {"local", "test"}:
            self._validate_local_kek()
            self._validate_local_endpoints()
        else:
            self._validate_nonlocal_environment()
        return self

    def _validate_local_kek(self) -> None:
        if self.credential_kek_provider != "local":
            raise ValueError("Local and test environments must use the local test KEK adapter")
        try:
            key = base64.b64decode(self.credential_kek_base64 or LOCAL_TEST_KEK, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("CREDENTIAL_KEK_BASE64 must be valid base64") from error
        if len(key) != 32:
            raise ValueError("The local test KEK must decode to exactly 32 bytes")

    def _validate_local_endpoints(self) -> None:
        for name, value in (
            ("DATABASE_URL", self.database_url),
            ("AUTH_DATABASE_URL", self.auth_database_url),
            ("WORKER_DATABASE_URL", self.worker_database_url),
            ("SCHEDULER_DATABASE_URL", self.scheduler_database_url),
            ("MIGRATION_DATABASE_URL", self.migration_database_url),
            ("BLOB_ENDPOINT_URL", self.blob_endpoint_url),
            ("OIDC_ISSUER", self.oidc_issuer),
            ("OIDC_REDIRECT_URI", self.oidc_redirect_uri),
            ("WEB_APP_ORIGIN", self.web_app_origin),
        ):
            parsed = urlparse(value or "")
            if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(f"{name} must use a loopback address in local/test")
        if not self.oidc_client_id or not self.oidc_client_secret:
            raise ValueError("Local/test OIDC client credentials must be configured")

    def _validate_nonlocal_environment(self) -> None:
        required = {
            "DATABASE_URL": self.database_url,
            "AUTH_DATABASE_URL": self.auth_database_url,
            "WORKER_DATABASE_URL": self.worker_database_url,
            "SCHEDULER_DATABASE_URL": self.scheduler_database_url,
            "MIGRATION_DATABASE_URL": self.migration_database_url,
            "BLOB_ENDPOINT_URL": self.blob_endpoint_url,
            "OIDC_ISSUER": self.oidc_issuer,
            "OIDC_CLIENT_ID": self.oidc_client_id,
            "OIDC_CLIENT_SECRET": self.oidc_client_secret,
            "OIDC_REDIRECT_URI": self.oidc_redirect_uri,
            "WEB_APP_ORIGIN": self.web_app_origin,
            "BETA_ALLOWED_EMAILS": self.beta_allowed_emails,
            "CHROME_EXTENSION_IDS": self.chrome_extension_ids,
            "APP_HASH_KEY": self.app_hash_key,
            "AUTH_TRANSACTION_ENCRYPTION_KEY": self.auth_transaction_encryption_key,
            "KEY_VAULT_CREDENTIAL_KEK_ID": self.key_vault_credential_kek_id,
        }
        missing = [
            name for name, value in required.items() if not value or self._is_placeholder(value)
        ]
        for name, attribute in (
            ("OIDC_CLIENT_ID", "oidc_client_id"),
            ("OIDC_CLIENT_SECRET", "oidc_client_secret"),
        ):
            if attribute not in self.model_fields_set and name not in missing:
                missing.append(name)
        if missing:
            raise ValueError(f"Missing production configuration: {', '.join(missing)}")
        if self.local_mocks_enabled:
            raise ValueError(
                "LOCAL_MOCKS_ENABLED must be false outside local and test environments"
            )
        if self.credential_kek_provider != "key_vault":
            raise ValueError("Nonlocal environments must use the Key Vault KEK adapter")
        if self.credential_kek_base64 is not None:
            raise ValueError("CREDENTIAL_KEK_BASE64 must not be configured outside local/test")

        for name, value in (
            ("DATABASE_URL", self.database_url),
            ("AUTH_DATABASE_URL", self.auth_database_url),
            ("WORKER_DATABASE_URL", self.worker_database_url),
            ("SCHEDULER_DATABASE_URL", self.scheduler_database_url),
            ("MIGRATION_DATABASE_URL", self.migration_database_url),
            ("BLOB_ENDPOINT_URL", self.blob_endpoint_url),
            ("OIDC_ISSUER", self.oidc_issuer),
            ("OIDC_REDIRECT_URI", self.oidc_redirect_uri),
            ("WEB_APP_ORIGIN", self.web_app_origin),
        ):
            parsed = urlparse(value or "")
            host = parsed.hostname
            if not host or host in {"localhost", "127.0.0.1", "::1", "mock-oidc", "wiremock"}:
                raise ValueError(f"{name} must use a configured nonlocal host outside local/test")
            if (
                name in {"BLOB_ENDPOINT_URL", "OIDC_ISSUER", "OIDC_REDIRECT_URI", "WEB_APP_ORIGIN"}
                and parsed.scheme != "https"
            ):
                raise ValueError(f"{name} must use HTTPS outside local/test")

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        lowered = value.strip().lower()
        return any(
            token in lowered
            for token in ("<", ">", "example", "change-me", "placeholder", "mock", "fake", ".test")
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings once per process."""
    values = {}
    for field in Settings.model_fields.values():
        if field.alias is not None and field.alias in os.environ:
            values[field.alias] = os.environ[field.alias]
    return Settings.model_validate(values)
