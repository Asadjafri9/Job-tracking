"""Owner-scoped rich profile facts API (PROF-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth, require_csrf
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.models import Profile, ProfileFact, ProfileFactVersion
from app.db.tenant import tenant_session

router = APIRouter(prefix="/api/v1", tags=["profile"])

MAX_CONFIRMED_FACTS = 200
JsonScalar = dict[str, Any] | list[Any] | str | int | float | bool | None
FactPurpose = Literal["AUTOFILL", "EMAIL", "MONITORING"]
ValueType = Literal["TEXT", "NUMBER", "DATE", "BOOLEAN", "URL", "JSON"]
Sensitivity = Literal["NORMAL", "SENSITIVE", "SPECIAL_CATEGORY"]


def _runtime_engine() -> Engine:
    settings = get_settings()
    return create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)


class FactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_key: str = Field(min_length=1, max_length=128)
    value_type: ValueType
    value: object = None
    sensitivity: Sensitivity = "NORMAL"
    allowed_purposes: list[FactPurpose] = Field(default_factory=list, max_length=3)


class FactUpdate(FactWrite):
    expected_revision: int = Field(ge=1)


class FactSummary(BaseModel):
    id: UUID
    fact_key: str
    value_type: str
    value: object
    sensitivity: str
    allowed_purposes: list[str]
    current_revision: int
    confirmation_state: str
    source_type: str
    updated_at: datetime


class ProfileResponse(BaseModel):
    revision: int
    facts: list[FactSummary]


def _fact_summary(fact: ProfileFact) -> FactSummary:
    latest = max(fact.versions, key=lambda version: version.revision, default=None)
    return FactSummary(
        id=fact.id,
        fact_key=fact.fact_key,
        value_type=fact.value_type,
        value=fact.value,
        sensitivity=fact.sensitivity,
        allowed_purposes=list(fact.allowed_purposes),
        current_revision=fact.current_revision,
        confirmation_state=latest.confirmation_state if latest else "REVIEW_REQUIRED",
        source_type=latest.source_type if latest else "MANUAL",
        updated_at=fact.updated_at,
    )


def _load_profile(session: Session, owner_id: UUID, *, lock: bool = False) -> Profile:
    statement = select(Profile).where(Profile.user_id == owner_id)
    if lock:
        statement = statement.with_for_update()
    profile = cast(Profile | None, session.scalar(statement))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile is not initialized")
    return profile


@router.get("/profile", response_model=ProfileResponse)
def get_profile(response: Response, auth: AuthContext = Depends(require_auth)) -> ProfileResponse:
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        profile = _load_profile(session, auth.user_id)
        facts = session.scalars(
            select(ProfileFact)
            .where(ProfileFact.user_id == auth.user_id, ProfileFact.is_active.is_(True))
            .order_by(ProfileFact.fact_key)
        ).all()
        response.headers["ETag"] = f'"{profile.current_revision}"'
        return ProfileResponse(
            revision=profile.current_revision, facts=[_fact_summary(fact) for fact in facts]
        )


def _bump_revision(profile: Profile) -> None:
    if profile.current_revision >= 2_147_483_647:
        raise HTTPException(status_code=409, detail="Profile revision limit reached")
    profile.current_revision += 1


def _validate_fact_write(body: FactWrite) -> str:
    fact_key = body.fact_key.strip().lower()
    if not fact_key:
        raise HTTPException(status_code=422, detail="fact_key is required")
    if body.sensitivity != "NORMAL" and body.allowed_purposes:
        raise HTTPException(
            status_code=422,
            detail="sensitive facts need explicit per-purpose consent via review",
        )
    if body.value is None:
        raise HTTPException(status_code=422, detail="a fact value is required")
    return fact_key


@router.put("/profile/facts", response_model=FactSummary, status_code=201)
def put_fact(
    body: FactWrite,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_auth),
) -> FactSummary:
    require_csrf(request, auth)
    fact_key = _validate_fact_write(body)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        profile = _load_profile(session, auth.user_id, lock=True)
        existing = session.scalar(
            select(ProfileFact).where(
                ProfileFact.user_id == auth.user_id,
                ProfileFact.profile_id == profile.id,
                ProfileFact.fact_key == fact_key,
            )
        )
        if existing is not None and existing.is_active:
            raise HTTPException(status_code=409, detail="fact already exists; update it instead")
        if existing is None:
            confirmed = int(
                session.scalar(
                    select(func.count())
                    .select_from(ProfileFact)
                    .where(ProfileFact.user_id == auth.user_id, ProfileFact.is_active.is_(True))
                )
                or 0
            )
            if confirmed >= MAX_CONFIRMED_FACTS:
                raise HTTPException(status_code=409, detail="profile fact limit reached")
            existing = ProfileFact(
                user_id=auth.user_id,
                profile_id=profile.id,
                fact_key=fact_key,
                value_type=body.value_type,
                value=body.value,
                sensitivity=body.sensitivity,
                allowed_purposes=list(body.allowed_purposes),
                current_revision=1,
                is_active=True,
            )
            session.add(existing)
            session.flush()
        else:
            existing.value_type = body.value_type
            existing.value = cast(JsonScalar, body.value)
            existing.sensitivity = body.sensitivity
            existing.allowed_purposes = list(body.allowed_purposes)
            existing.current_revision += 1
            existing.is_active = True
        session.add(
            ProfileFactVersion(
                user_id=auth.user_id,
                profile_fact_id=existing.id,
                revision=existing.current_revision,
                value=body.value,
                source_type="MANUAL",
                confirmation_state="CONFIRMED",
                confirmed_at=datetime.now(UTC),
            )
        )
        _bump_revision(profile)
        session.flush()
        response.headers["ETag"] = f'"{profile.current_revision}"'
        return _fact_summary(existing)


@router.post("/profile/facts/{fact_id}", response_model=FactSummary)
def update_fact(
    fact_id: UUID,
    body: FactUpdate,
    request: Request,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    auth: AuthContext = Depends(require_auth),
) -> FactSummary:
    require_csrf(request, auth)
    if if_match != f'"{body.expected_revision}"':
        raise HTTPException(status_code=409, detail="Fact revision changed")
    fact_key = _validate_fact_write(body)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        profile = _load_profile(session, auth.user_id, lock=True)
        fact = session.scalar(
            select(ProfileFact)
            .where(ProfileFact.user_id == auth.user_id, ProfileFact.id == fact_id)
            .with_for_update()
        )
        if fact is None or not fact.is_active:
            raise HTTPException(status_code=404, detail="Fact not found")
        if fact.current_revision != body.expected_revision:
            raise HTTPException(status_code=409, detail="Fact revision changed")
        fact.fact_key = fact_key
        fact.value_type = body.value_type
        fact.value = cast(JsonScalar, body.value)
        fact.sensitivity = body.sensitivity
        fact.allowed_purposes = list(body.allowed_purposes)
        fact.current_revision += 1
        session.add(
            ProfileFactVersion(
                user_id=auth.user_id,
                profile_fact_id=fact.id,
                revision=fact.current_revision,
                value=body.value,
                source_type="MANUAL",
                confirmation_state="CONFIRMED",
                confirmed_at=datetime.now(UTC),
            )
        )
        _bump_revision(profile)
        session.flush()
        response.headers["ETag"] = f'"{profile.current_revision}"'
        return _fact_summary(fact)


@router.delete("/profile/facts/{fact_id}", status_code=204)
def delete_fact(
    fact_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> Response:
    require_csrf(request, auth)
    with tenant_session(_runtime_engine(), auth.user_id) as session:
        profile = _load_profile(session, auth.user_id, lock=True)
        fact = session.scalar(
            select(ProfileFact)
            .where(ProfileFact.user_id == auth.user_id, ProfileFact.id == fact_id)
            .with_for_update()
        )
        if fact is None or not fact.is_active:
            raise HTTPException(status_code=404, detail="Fact not found")
        fact.is_active = False
        fact.current_revision += 1
        _bump_revision(profile)
    return Response(status_code=204)


def confirmed_facts_for_purpose(
    session: Session, owner_id: UUID, purpose: str
) -> list[ProfileFact]:
    """Facts eligible for provider context: active, confirmed, purpose-tagged,
    and never SENSITIVE/SPECIAL_CATEGORY unless explicitly purpose-consented."""
    facts = session.scalars(
        select(ProfileFact).where(
            ProfileFact.user_id == owner_id, ProfileFact.is_active.is_(True)
        )
    ).all()
    eligible = []
    for fact in facts:
        if purpose not in (fact.allowed_purposes or []):
            continue
        if fact.sensitivity != "NORMAL":
            continue
        latest = max(fact.versions, key=lambda version: version.revision, default=None)
        if latest is not None and latest.confirmation_state == "CONFIRMED":
            eligible.append(fact)
    return eligible[:40]
