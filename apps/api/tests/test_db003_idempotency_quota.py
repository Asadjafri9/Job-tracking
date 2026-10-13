"""PostgreSQL concurrency checks for DB-003 (requires an opted-in local DB)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.connection import sqlalchemy_url
from app.db.idempotency import (
    IdempotencyConflict,
    claim_idempotency,
    conditional_revision_update,
    reserve_quota,
)
from app.db.models import Profile, User

DATABASE_URL = os.getenv("DB001_DATABASE_URL")
if DATABASE_URL is None:
    pytest.skip("DB001_DATABASE_URL is not configured", allow_module_level=True)
if urlparse(DATABASE_URL).hostname not in {"localhost", "127.0.0.1", "::1"}:
    pytest.skip("DB-003 database tests are restricted to loopback", allow_module_level=True)

engine: Engine = create_engine(sqlalchemy_url(DATABASE_URL), pool_pre_ping=True)


@pytest.fixture
def owner_profile() -> tuple[UUID, UUID]:
    owner_id = uuid4()
    profile_id = uuid4()
    with Session(engine) as session, session.begin():
        owner = User(
            id=owner_id,
            issuer="https://db003.local.test/issuer",
            subject=str(uuid4()),
            directory_object_id=uuid4(),
            login_email=f"{owner_id}@example.test",
            login_email_verified=True,
        )
        session.add(owner)
        session.flush()
        session.add(Profile(id=profile_id, user_id=owner_id))
    try:
        yield owner_id, profile_id
    finally:
        with engine.begin() as connection:
            connection.execute(delete(User).where(User.id == owner_id))


def test_idempotency_key_reuse_returns_one_record_and_rejects_changed_input(
    owner_profile: tuple[UUID, UUID],
) -> None:
    owner_id, _ = owner_profile
    key = uuid4()
    fingerprint = "a" * 64

    def claim() -> tuple[bool, UUID]:
        with Session(engine) as session, session.begin():
            result = claim_idempotency(
                session,
                owner_id=owner_id,
                route_key="profile.update",
                key=key,
                input_fingerprint=fingerprint,
            )
            return result.created, result.record.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(created for created, _ in results) == [False, True]
    assert results[0][1] == results[1][1]

    with Session(engine) as session, session.begin():
        with pytest.raises(IdempotencyConflict, match="different input"):
            claim_idempotency(
                session,
                owner_id=owner_id,
                route_key="profile.update",
                key=key,
                input_fingerprint="b" * 64,
            )


def test_revision_update_rejects_stale_writer(owner_profile: tuple[UUID, UUID]) -> None:
    owner_id, profile_id = owner_profile
    with Session(engine) as session, session.begin():
        assert (
            conditional_revision_update(
                session,
                model=Profile,
                owner_id=owner_id,
                entity_id=profile_id,
                revision_field="current_revision",
                expected_revision=1,
                values={},
            )
            == 2
        )

    with Session(engine) as session, session.begin():
        with pytest.raises(IdempotencyConflict, match="revision conflict"):
            conditional_revision_update(
                session,
                model=Profile,
                owner_id=owner_id,
                entity_id=profile_id,
                revision_field="current_revision",
                expected_revision=1,
                values={},
            )


def test_quota_reservations_serialize_competing_requests(
    owner_profile: tuple[UUID, UUID],
) -> None:
    owner_id, _ = owner_profile

    def reserve(_: int) -> str:
        try:
            with Session(engine) as session, session.begin():
                reserve_quota(
                    session,
                    owner_id=owner_id,
                    kind="documents",
                    reservation_key=uuid4(),
                    amount=6,
                    committed_usage=0,
                    maximum=10,
                )
            return "reserved"
        except IdempotencyConflict:
            return "quota_exceeded"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sorted(results) == ["quota_exceeded", "reserved"]
