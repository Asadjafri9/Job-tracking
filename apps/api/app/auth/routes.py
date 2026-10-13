"""OIDC login, opaque web sessions, logout, and extension grant exchange."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DbSession

from app.auth.oidc import OIDCError, authorization_url, discover, exchange_code, verify_id_token
from app.auth.sessions import (
    AuthenticationError,
    authenticate_session,
    consume_extension_grant,
    create_session,
    csrf_token,
    issue_extension_grant,
    revoke_all_sessions,
    verify_csrf,
)
from app.auth.transactions import consume_transaction, create_transaction
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import Profile, User

router = APIRouter(prefix="/auth", tags=["auth"])
_EXTENSION_ID = re.compile(r"^[a-p]{32}$")
_COOKIE = "__Host-copilot_session"
_TX_COOKIE = "__Host-copilot_auth_tx"


@lru_cache(maxsize=1)
def _engine() -> Engine:
    settings = get_settings()
    return create_engine(sqlalchemy_url(settings.auth_database_url), pool_pre_ping=True)


def _db() -> Iterator[DbSession]:
    with _engine().connect() as connection:
        with DbSession(bind=connection) as session:
            try:
                if session.scalar(text("SELECT current_user")) != "copilot_auth":
                    raise RuntimeError(
                        "authentication routes require the copilot_auth database role"
                    )
                yield session
                if session.in_transaction():
                    session.commit()
            except Exception:
                session.rollback()
                raise


def _transaction_key() -> bytes:
    settings = get_settings()
    source = settings.auth_transaction_encryption_key or settings.oidc_client_secret or ""
    return hashlib.sha256(source.encode() + b"\x00oidc-transaction-key").digest()


def _csrf_key() -> bytes:
    settings = get_settings()
    source = settings.app_hash_key or settings.oidc_client_secret or ""
    return hashlib.sha256(source.encode() + b"\x00csrf-key").digest()


def _allowed_extension(extension_id: str) -> bool:
    settings = get_settings()
    allowed = {item.strip() for item in settings.chrome_extension_ids.split(",") if item.strip()}
    return bool(_EXTENSION_ID.fullmatch(extension_id) and extension_id in allowed)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _COOKIE,
        token,
        max_age=12 * 60 * 60,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )


class ExtensionExchange(BaseModel):
    model_config = {"extra": "forbid"}
    grant: str = Field(min_length=32, max_length=128)
    state: str = Field(min_length=16, max_length=128)
    code_verifier: str = Field(min_length=43, max_length=128)


class SessionResponse(BaseModel):
    user_id: UUID
    login_email: str
    csrf_token: str
    auth_time: datetime


class ExtensionTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime


class AuthContext(BaseModel):
    user_id: UUID
    token: str
    auth_time: datetime
    is_extension: bool = False


def require_auth(request: Request, db: DbSession = Depends(_db)) -> AuthContext:
    authorization = request.headers.get("Authorization", "")
    is_extension = bool(authorization)
    if is_extension:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication is required")
        token = authorization[7:]
        origin = request.headers.get("Origin", "")
        prefix = "chrome-extension://"
        if not origin.startswith(prefix) or not _allowed_extension(origin.removeprefix(prefix)):
            raise HTTPException(status_code=403, detail="Extension is not registered")
    else:
        token = request.cookies.get(_COOKIE, "")
    try:
        row = authenticate_session(
            db, token, expected_client_type="EXTENSION" if is_extension else "WEB"
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail="Authentication is required") from error
    return AuthContext(
        user_id=row.user_id, token=token, auth_time=row.auth_time, is_extension=is_extension
    )


def require_csrf(request: Request, auth: AuthContext) -> None:
    origin = request.headers.get("Origin", "")
    if auth.is_extension:
        if not origin.startswith("chrome-extension://") or not _allowed_extension(
            origin.removeprefix("chrome-extension://")
        ):
            raise HTTPException(status_code=403, detail="Extension is not registered")
        return
    if origin != get_settings().web_app_origin.rstrip("/") or not verify_csrf(
        auth.token, request.headers.get("X-CSRF-Token", ""), _csrf_key()
    ):
        raise HTTPException(status_code=403, detail="Request verification failed")


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required")
    return authorization[7:]


@router.get("/login", include_in_schema=True)
def login(
    request: Request,
    extension_id: str | None = None,
    extension_state: str | None = None,
    extension_challenge: str | None = None,
    fresh: bool = False,
    db: DbSession = Depends(_db),
) -> RedirectResponse:
    settings = get_settings()
    if (extension_id is None) != (extension_state is None) or (extension_id is None) != (
        extension_challenge is None
    ):
        raise HTTPException(status_code=400, detail="Incomplete extension login parameters")
    callback_uri = settings.oidc_redirect_uri or ""
    binding = secrets.token_urlsafe(32)
    if extension_id is not None:
        if not _allowed_extension(extension_id):
            raise HTTPException(status_code=400, detail="Extension is not registered")
        if not 43 <= len(extension_challenge or "") <= 128:
            raise HTTPException(status_code=400, detail="Invalid extension PKCE challenge")
    try:
        metadata = discover(settings.oidc_issuer or "")
        row, state, nonce, verifier = create_transaction(
            db,
            encryption_key=_transaction_key(),
            browser_binding_hash=hashlib.sha256(binding.encode()).hexdigest(),
            callback_uri=callback_uri,
            client_id=settings.oidc_client_id or "",
            extension_id=extension_id,
            extension_pkce_challenge=extension_challenge,
            extension_state=extension_state,
            require_fresh_auth=fresh,
        )
        del row
        redirect = authorization_url(
            metadata=metadata,
            client_id=settings.oidc_client_id or "",
            redirect_uri=callback_uri,
            state=state,
            nonce=nonce,
            verifier=verifier,
            fresh=fresh,
        )
    except (OIDCError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Identity service is unavailable") from error
    response = RedirectResponse(redirect, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        _TX_COOKIE, binding, max_age=600, secure=True, httponly=True, samesite="lax", path="/"
    )
    return response


@router.get("/callback", include_in_schema=True)
def callback(
    request: Request,
    code: str,
    state: str,
    db: DbSession = Depends(_db),
) -> Response:
    settings = get_settings()
    try:
        transaction, verifier = consume_transaction(
            db, state=state, encryption_key=_transaction_key()
        )
        binding = request.cookies.get(_TX_COOKIE, "")
        if not binding or not hmac.compare_digest(
            hashlib.sha256(binding.encode()).hexdigest(), transaction.browser_binding_hash
        ):
            raise AuthenticationError("browser transaction binding failed")
        db.commit()
        if (
            transaction.client_id != settings.oidc_client_id
            or transaction.callback_uri != settings.oidc_redirect_uri
        ):
            raise AuthenticationError("OIDC client binding failed")
        metadata = discover(settings.oidc_issuer or "")
        token = exchange_code(
            metadata=metadata,
            client_id=settings.oidc_client_id or "",
            client_secret=settings.oidc_client_secret or "",
            redirect_uri=transaction.callback_uri,
            code=code,
            verifier=verifier,
        )
        claims = verify_id_token(
            token,
            metadata=metadata,
            client_id=settings.oidc_client_id or "",
            client_secret=settings.oidc_client_secret or "",
            expected_nonce_hash=transaction.nonce_hash,
            local_test=settings.app_env in {"local", "test"},
        )
        if transaction.require_fresh_auth:
            auth_time = claims.get("auth_time")
            now_timestamp = datetime.now(UTC).timestamp()
            if (
                not isinstance(auth_time, (int, float))
                or auth_time > now_timestamp
                or now_timestamp - auth_time > 600
            ):
                raise AuthenticationError("fresh provider authentication is required")
        directory_id = UUID(str(claims.get("oid", "")))
        email = str(claims["email"]).strip().casefold()
        allowed_emails = {
            value.strip().casefold()
            for value in settings.beta_allowed_emails.split(",")
            if value.strip()
        }
        if email not in allowed_emails:
            raise AuthenticationError("account is not enrolled for beta")
        user = db.scalar(
            select(User).where(User.issuer == settings.oidc_issuer, User.subject == claims["sub"])
        )
        if user is None:
            user_id = db.scalar(
                pg_insert(User)
                .values(
                    issuer=settings.oidc_issuer or "",
                    subject=str(claims["sub"]),
                    directory_object_id=directory_id,
                    login_email=email,
                    login_email_verified=True,
                    beta_eligible=True,
                    state="ACTIVE",
                )
                .on_conflict_do_nothing(constraint="uq_users_issuer_subject")
                .returning(User.id)
            )
            user = (
                db.get(User, user_id)
                if user_id is not None
                else db.scalar(
                    select(User).where(
                        User.issuer == settings.oidc_issuer, User.subject == claims["sub"]
                    )
                )
            )
            if user is None:
                raise AuthenticationError("account enrollment failed")
        if user.directory_object_id != directory_id or user.login_email != email:
            raise AuthenticationError("identity mapping changed; account access denied")
        if user.state != "ACTIVE" or not user.beta_eligible:
            raise AuthenticationError("account is unavailable")
        db.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user.id)}
        )
        db.execute(
            pg_insert(Profile)
            .values(user_id=user.id, current_revision=1)
            .on_conflict_do_nothing(constraint="uq_profiles_user_id")
        )
        issued = create_session(
            db,
            user_id=user.id,
            auth_time=datetime.fromtimestamp(int(claims["auth_time"]), UTC)
            if isinstance(claims.get("auth_time"), (int, float))
            else datetime.now(UTC),
            csrf_hash_key=_csrf_key(),
        )
        if transaction.extension_id:
            if not _allowed_extension(transaction.extension_id) or not transaction.extension_state:
                raise AuthenticationError("extension transaction is invalid")
            grant, _ = issue_extension_grant(
                db,
                user_id=user.id,
                session_id=issued.session_id,
                client_id="job-tracking-extension",
                extension_id=transaction.extension_id,
                pkce_challenge=transaction.extension_pkce_challenge or "",
                state=transaction.extension_state,
            )
            extension_url = f"https://{transaction.extension_id}.chromiumapp.org/auth"
            query = urlencode({"grant": grant, "state": transaction.extension_state})
            redirect_response = RedirectResponse(f"{extension_url}?{query}", status_code=302)
            redirect_response.delete_cookie(
                _TX_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
            )
            return redirect_response
        redirect = RedirectResponse(settings.web_app_origin, status_code=302)
        _set_cookie(redirect, issued.token)
        redirect.delete_cookie(_TX_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        return redirect
    except (OIDCError, AuthenticationError, ValueError, KeyError) as error:
        raise HTTPException(status_code=401, detail="Sign-in could not be completed") from error


@router.get("/session", response_model=SessionResponse)
def current_session(request: Request, db: DbSession = Depends(_db)) -> SessionResponse:
    raw_token = request.cookies.get(_COOKIE, "")
    try:
        row = authenticate_session(db, raw_token)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail="Authentication is required") from error
    user = db.scalar(select(User).where(User.id == row.user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication is required")
    return SessionResponse(
        user_id=user.id,
        login_email=user.login_email,
        csrf_token=csrf_token(raw_token, _csrf_key()),
        auth_time=row.auth_time,
    )


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession = Depends(_db)) -> Response:
    raw_token = request.cookies.get(_COOKIE, "")
    if raw_token:
        try:
            row = authenticate_session(db, raw_token)
            supplied_csrf = request.headers.get("X-CSRF-Token", "")
            origin = request.headers.get("Origin", "")
            if origin != get_settings().web_app_origin.rstrip("/") or not verify_csrf(
                raw_token, supplied_csrf, _csrf_key()
            ):
                raise HTTPException(status_code=403, detail="Request verification failed")
            revoke_all_sessions(db, row.user_id)
        except AuthenticationError:
            pass
    response.delete_cookie(_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    response.status_code = 204
    return response


@router.post("/extension/exchange", response_model=ExtensionTokenResponse)
def extension_exchange(
    body: ExtensionExchange,
    request: Request,
    response: Response,
    db: DbSession = Depends(_db),
) -> ExtensionTokenResponse:
    origin = request.headers.get("Origin", "")
    prefix = "chrome-extension://"
    if not origin.startswith(prefix):
        raise HTTPException(status_code=403, detail="Extension origin is required")
    extension_id = origin[len(prefix) :]
    if not _allowed_extension(extension_id):
        raise HTTPException(status_code=403, detail="Extension is not registered")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    try:
        issued = consume_extension_grant(
            db,
            grant=body.grant,
            client_id="job-tracking-extension",
            extension_id=extension_id,
            state=body.state,
            expected_state=body.state,
            verifier=body.code_verifier,
        )
    except (AuthenticationError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Extension grant is invalid") from error
    return ExtensionTokenResponse(access_token=issued.token, expires_at=issued.expires_at)


@router.options("/extension/exchange", include_in_schema=False)
def extension_exchange_preflight(request: Request) -> Response:
    origin = request.headers.get("Origin", "")
    if not origin.startswith("chrome-extension://") or not _allowed_extension(
        origin.removeprefix("chrome-extension://")
    ):
        raise HTTPException(status_code=403, detail="Extension is not registered")
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "300",
            "Vary": "Origin",
        },
    )


@router.post("/extension/logout", status_code=204)
def extension_logout(
    request: Request, response: Response, db: DbSession = Depends(_db)
) -> Response:
    origin = request.headers.get("Origin", "")
    prefix = "chrome-extension://"
    if not origin.startswith(prefix) or not _allowed_extension(origin.removeprefix(prefix)):
        raise HTTPException(status_code=403, detail="Extension is not registered")
    token = _bearer_token(request)
    try:
        session = authenticate_session(db, token, expected_client_type="EXTENSION")
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail="Authentication is required") from error
    revoke_all_sessions(db, session.user_id)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    response.status_code = 204
    return response


@router.options("/extension/logout", include_in_schema=False)
def extension_logout_preflight(request: Request) -> Response:
    origin = request.headers.get("Origin", "")
    prefix = "chrome-extension://"
    if not origin.startswith(prefix) or not _allowed_extension(origin.removeprefix(prefix)):
        raise HTTPException(status_code=403, detail="Extension is not registered")
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization",
            "Access-Control-Max-Age": "300",
            "Vary": "Origin",
        },
    )
