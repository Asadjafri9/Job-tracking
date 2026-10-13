"""Owner-scoped saved provider key and consent settings APIs."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Engine

from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import LOCAL_TEST_KEK, get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import ProviderCredential, ProviderRoute, ProviderSettings
from app.db.tenant import tenant_session
from app.security.credentials import (
    CredentialSummary,
    revoke_credential,
    store_credential,
    summarize,
)
from app.security.key_encryption import (
    KeyEncryptionError,
    KeyEncryptionProvider,
    KeyVaultKeyEncryption,
    LocalAesGcmKeyEncryption,
)

router = APIRouter(prefix="/api/v1", tags=["credentials"])
ProviderName = Literal["OPENROUTER", "XAI", "GEMINI"]


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    settings = get_settings()
    return create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)


def _key_encryption_provider() -> KeyEncryptionProvider:
    settings = get_settings()
    if settings.credential_kek_provider == "key_vault":
        if not settings.key_vault_credential_kek_id:
            raise HTTPException(status_code=503, detail="Credential key service is not configured")
        try:
            return KeyVaultKeyEncryption(settings.key_vault_credential_kek_id)
        except ValueError as error:
            raise HTTPException(
                status_code=503, detail="Credential key service is misconfigured"
            ) from error
    encoded = settings.credential_kek_base64 or LOCAL_TEST_KEK
    return LocalAesGcmKeyEncryption(base64.b64decode(encoded, validate=True), "local-test-v1")


class CredentialWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr = Field(min_length=1, max_length=4096)
    allow_interactive: bool
    allow_background: bool = False


class CredentialList(BaseModel):
    credentials: list[CredentialSummary]


class RouteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential_id: UUID
    model_id: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    interactive_enabled: bool = True
    background_enabled: bool = False


class ProviderSettingsWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    interactive_consent: bool
    fallback_consent: bool
    background_consent: bool
    routes: list[RouteWrite] = Field(max_length=3)


class ProviderSettingsResponse(BaseModel):
    revision: int
    interactive_consent: bool
    fallback_consent: bool
    background_consent: bool
    routes: list[RouteWrite]


def _fresh(auth: AuthContext) -> None:
    if datetime.now(UTC) - auth.auth_time > timedelta(minutes=10):
        raise HTTPException(status_code=403, detail="Fresh sign-in is required")


@router.get("/provider-credentials", response_model=CredentialList)
def list_credentials(auth: AuthContext = Depends(require_auth)) -> CredentialList:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        rows = session.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.user_id == auth.user_id)
            .order_by(ProviderCredential.provider)
        ).all()
        return CredentialList(credentials=[summarize(row) for row in rows])


@router.put("/provider-credentials/{provider}", response_model=CredentialSummary)
def put_credential(
    provider: ProviderName,
    body: CredentialWrite,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> CredentialSummary:
    require_csrf(request, auth)
    _fresh(auth)
    try:
        with tenant_session(_runtime_engine(), auth.user_id) as session:
            current = session.scalar(
                select(ProviderCredential).where(
                    ProviderCredential.user_id == auth.user_id,
                    ProviderCredential.provider == provider,
                )
            )
            if current is None:
                count = (
                    session.scalar(
                        select(func.count())
                        .select_from(ProviderCredential)
                        .where(
                            ProviderCredential.user_id == auth.user_id,
                            ProviderCredential.status != "REVOKED",
                        )
                    )
                    or 0
                )
                if count >= 3:
                    raise HTTPException(status_code=409, detail="Provider credential limit reached")
            return store_credential(
                session,
                owner_id=auth.user_id,
                provider=provider,
                api_key=body.api_key.get_secret_value(),
                key_encryption=_key_encryption_provider(),
                allow_interactive=body.allow_interactive,
                allow_background=body.allow_background,
            )
    except KeyEncryptionError as error:
        raise HTTPException(
            status_code=503, detail="Credential key service is unavailable"
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Credential could not be saved") from error


@router.delete("/provider-credentials/{credential_id}", status_code=204)
def delete_credential(
    credential_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> Response:
    require_csrf(request, auth)
    _fresh(auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        if not revoke_credential(session, owner_id=auth.user_id, credential_id=credential_id):
            raise HTTPException(status_code=404, detail="Credential not found")
        session.execute(
            delete(ProviderRoute).where(
                ProviderRoute.user_id == auth.user_id,
                ProviderRoute.credential_id == credential_id,
            )
        )
        settings = session.scalar(
            select(ProviderSettings)
            .where(ProviderSettings.user_id == auth.user_id)
            .with_for_update()
        )
        if settings is not None:
            if settings.revision >= 2_147_483_647:
                raise HTTPException(
                    status_code=409, detail="Provider settings revision limit reached"
                )
            settings.revision += 1
            settings.interactive_consent_revision = None
            settings.fallback_consent_revision = None
            settings.background_consent_revision = None
    return Response(status_code=204)


@router.get("/provider-settings", response_model=ProviderSettingsResponse)
def get_provider_settings(
    response: Response, auth: AuthContext = Depends(require_auth)
) -> ProviderSettingsResponse:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        settings = session.scalar(
            select(ProviderSettings).where(ProviderSettings.user_id == auth.user_id)
        )
        routes = session.scalars(
            select(ProviderRoute)
            .where(ProviderRoute.user_id == auth.user_id)
            .order_by(ProviderRoute.position)
        ).all()
        revision = settings.revision if settings else 1
        response.headers["ETag"] = f'"{revision}"'
        return ProviderSettingsResponse(
            revision=revision,
            interactive_consent=bool(settings and settings.interactive_consent_revision),
            fallback_consent=bool(settings and settings.fallback_consent_revision),
            background_consent=bool(settings and settings.background_consent_revision),
            routes=[
                RouteWrite(
                    credential_id=row.credential_id,
                    model_id=row.model_id,
                    enabled=row.enabled,
                    interactive_enabled=row.interactive_enabled,
                    background_enabled=row.background_enabled,
                )
                for row in routes
            ],
        )


@router.put("/provider-settings", response_model=ProviderSettingsResponse)
def put_provider_settings(
    body: ProviderSettingsWrite,
    request: Request,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    auth: AuthContext = Depends(require_auth),
) -> ProviderSettingsResponse:
    require_csrf(request, auth)
    if if_match != f'"{body.expected_revision}"':
        raise HTTPException(status_code=409, detail="Provider settings revision changed")
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        settings = session.scalar(
            select(ProviderSettings)
            .where(ProviderSettings.user_id == auth.user_id)
            .with_for_update()
        )
        if settings is None:
            if body.expected_revision != 1:
                raise HTTPException(status_code=409, detail="Provider settings revision changed")
            settings = ProviderSettings(user_id=auth.user_id, revision=1)
            session.add(settings)
            session.flush()
        elif settings.revision != body.expected_revision:
            raise HTTPException(status_code=409, detail="Provider settings revision changed")
        if len({route.credential_id for route in body.routes}) != len(body.routes):
            raise HTTPException(status_code=422, detail="A credential may appear only once")
        credentials = {
            row.id: row
            for row in session.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.user_id == auth.user_id,
                    ProviderCredential.enabled.is_(True),
                    ProviderCredential.status == "READY",
                    ProviderCredential.revoked_at.is_(None),
                )
            ).all()
        }
        for route in body.routes:
            credential = credentials.get(route.credential_id)
            if credential is None:
                raise HTTPException(status_code=404, detail="Provider credential not found")
            if (
                route.enabled
                and route.interactive_enabled
                and (not body.interactive_consent or not credential.allow_interactive)
            ):
                raise HTTPException(
                    status_code=403, detail="Interactive provider consent is required"
                )
            if (
                route.enabled
                and route.background_enabled
                and (not body.background_consent or not credential.allow_background)
            ):
                raise HTTPException(
                    status_code=403, detail="Background provider consent is required"
                )
        enabled_routes = [route for route in body.routes if route.enabled]
        if len(enabled_routes) > 1 and not body.fallback_consent:
            raise HTTPException(status_code=403, detail="Fallback consent is required")
        if settings.revision >= 2_147_483_647:
            raise HTTPException(status_code=409, detail="Provider settings revision limit reached")
        settings.revision += 1
        settings.interactive_consent_revision = (
            settings.revision if body.interactive_consent else None
        )
        settings.fallback_consent_revision = settings.revision if body.fallback_consent else None
        settings.background_consent_revision = (
            settings.revision if body.background_consent else None
        )
        session.query(ProviderRoute).filter_by(user_id=auth.user_id).delete()
        for position, route in enumerate(body.routes, start=1):
            credential = credentials[route.credential_id]
            session.add(
                ProviderRoute(
                    user_id=auth.user_id,
                    credential_id=route.credential_id,
                    position=position,
                    model_id=route.model_id,
                    enabled=route.enabled,
                    interactive_enabled=route.interactive_enabled,
                    background_enabled=route.background_enabled,
                )
            )
        session.flush()
        response.headers["ETag"] = f'"{settings.revision}"'
        return ProviderSettingsResponse(
            revision=settings.revision,
            interactive_consent=body.interactive_consent,
            fallback_consent=body.fallback_consent,
            background_consent=body.background_consent,
            routes=body.routes,
        )
