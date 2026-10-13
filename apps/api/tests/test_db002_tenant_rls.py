"""PostgreSQL integration checks for DB-002 tenant isolation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from app.db.connection import sqlalchemy_url
from app.db.tenant import tenant_session

MIGRATION_DATABASE_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_DATABASE_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
AUTH_DATABASE_URL = os.getenv("DB002_AUTH_DATABASE_URL")
WORKER_DATABASE_URL = os.getenv("DB002_WORKER_DATABASE_URL")
if MIGRATION_DATABASE_URL is None or RUNTIME_DATABASE_URL is None:
    pytest.skip("DB-002 requires migration and runtime database URLs", allow_module_level=True)
for _url in (MIGRATION_DATABASE_URL, RUNTIME_DATABASE_URL):
    if urlparse(_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("DB-002 database tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_DATABASE_URL))
runtime_engine: Engine = create_engine(
    sqlalchemy_url(RUNTIME_DATABASE_URL), pool_size=1, max_overflow=0
)
auth_engine: Engine | None = (
    create_engine(sqlalchemy_url(AUTH_DATABASE_URL)) if AUTH_DATABASE_URL else None
)
worker_engine: Engine | None = (
    create_engine(sqlalchemy_url(WORKER_DATABASE_URL)) if WORKER_DATABASE_URL else None
)


def _create_owner(owner_id: UUID) -> UUID:
    profile_id = uuid4()
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                "VALUES (:id, :issuer, :subject, :directory_id, :email, true)"
            ),
            {
                "id": owner_id,
                "issuer": "urn:db002:test",
                "subject": str(owner_id),
                "directory_id": uuid4(),
                "email": f"{owner_id}@example.test",
            },
        )
        connection.execute(
            text("INSERT INTO profiles (id, user_id, current_revision) VALUES (:id, :owner, 1)"),
            {"id": profile_id, "owner": owner_id},
        )
    return profile_id


@pytest.fixture
def two_owners() -> Iterator[tuple[UUID, UUID, UUID, UUID]]:
    owner_a, owner_b = uuid4(), uuid4()
    profile_a = _create_owner(owner_a)
    profile_b = _create_owner(owner_b)
    try:
        yield owner_a, owner_b, profile_a, profile_b
    finally:
        with migration_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM users WHERE id IN (:owner_a, :owner_b)"),
                {"owner_a": owner_a, "owner_b": owner_b},
            )


def test_runtime_role_is_restricted_and_does_not_own_protected_tables() -> None:
    with runtime_engine.connect() as connection:
        role = connection.execute(
            text(
                "SELECT r.rolname, r.rolsuper, r.rolbypassrls, "
                "c.relrowsecurity, owner.rolname AS table_owner "
                "FROM pg_roles r CROSS JOIN pg_class c "
                "JOIN pg_roles owner ON owner.oid = c.relowner "
                "WHERE r.rolname = current_user AND c.oid = 'public.profiles'::regclass"
            )
        ).one()
        assert role.rolname == "copilot_runtime"
        assert not role.rolsuper
        assert not role.rolbypassrls
        assert role.relrowsecurity
        assert role.table_owner != role.rolname
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT id FROM users LIMIT 1"))


def test_missing_tenant_context_cannot_read_or_write_tenant_rows(
    two_owners: tuple[UUID, UUID, UUID, UUID],
) -> None:
    owner_a, _, profile_a, _ = two_owners
    with runtime_engine.connect() as connection:
        with connection.begin():
            assert connection.scalar(text("SELECT count(*) FROM profiles")) == 0
            result = connection.execute(
                text("UPDATE profiles SET current_revision = 2 WHERE id = :id"),
                {"id": profile_a},
            )
            assert result.rowcount == 0
        with pytest.raises(DBAPIError):
            with connection.begin():
                connection.execute(
                    text(
                        "INSERT INTO profiles (id, user_id, current_revision) "
                        "VALUES (:id, :owner, 1)"
                    ),
                    {"id": uuid4(), "owner": owner_a},
                )


def test_tenant_context_limits_reads_and_rejects_cross_owner_writes(
    two_owners: tuple[UUID, UUID, UUID, UUID],
) -> None:
    owner_a, owner_b, profile_a, profile_b = two_owners
    with tenant_session(runtime_engine, owner_a) as session:
        rows = session.execute(text("SELECT user_id, id FROM profiles ORDER BY id")).all()
        assert rows == [(owner_a, profile_a)]
    with pytest.raises(DBAPIError):
        with tenant_session(runtime_engine, owner_a) as session:
            session.execute(
                text("UPDATE profiles SET user_id = :other WHERE id = :id"),
                {"other": owner_b, "id": profile_a},
            )

    with tenant_session(runtime_engine, owner_b) as session:
        rows = session.execute(text("SELECT user_id, id FROM profiles")).all()
        assert rows == [(owner_b, profile_b)]


def test_tenant_context_is_cleared_after_commit_and_rollback(
    two_owners: tuple[UUID, UUID, UUID, UUID],
) -> None:
    owner_a, _, _, _ = two_owners
    with runtime_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(owner_a)}
        )
        assert connection.scalar(text("SELECT count(*) FROM profiles")) == 1
        transaction.commit()

        with connection.begin():
            assert connection.scalar(text("SELECT count(*) FROM profiles")) == 0

        transaction = connection.begin()
        connection.execute(
            text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(owner_a)}
        )
        assert connection.scalar(text("SELECT count(*) FROM profiles")) == 1
        transaction.rollback()

        with connection.begin():
            assert connection.scalar(text("SELECT count(*) FROM profiles")) == 0


def test_tenant_session_requires_a_uuid() -> None:
    with pytest.raises(TypeError):
        with tenant_session(runtime_engine, "not-a-uuid"):  # type: ignore[arg-type]
            pass


def test_every_owner_scoped_table_has_runtime_row_security() -> None:
    with migration_engine.connect() as connection:
        owner_scoped_tables = set(
            connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name = 'user_id'"
                )
            )
        )
        protected_tables = set(
            connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity")
            )
        )
        runtime_policy_tables = set(
            connection.scalars(
                text(
                    "SELECT tablename FROM pg_policies "
                    "WHERE schemaname = 'public' "
                    "AND policyname LIKE 'tenant_isolation_%' "
                    "AND 'copilot_runtime' = ANY(roles)"
                )
            )
        )
        assert owner_scoped_tables <= protected_tables
        assert owner_scoped_tables <= runtime_policy_tables


def test_auth_and_worker_roles_have_narrow_bootstrap_access() -> None:
    if auth_engine is None or worker_engine is None:
        pytest.skip("DB-002 auth/worker role URLs were not provided")
    with auth_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "copilot_auth"
        connection.execute(text("SELECT id FROM users LIMIT 0"))
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT id FROM documents LIMIT 0"))
    with worker_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "copilot_worker"
        connection.execute(text("SELECT id FROM jobs LIMIT 0"))
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT id FROM profiles LIMIT 0"))


def test_auth_role_requires_a_hash_context_to_read_sessions(
    two_owners: tuple[UUID, UUID, UUID, UUID],
) -> None:
    if auth_engine is None:
        pytest.skip("DB-002 auth role URL was not provided")
    owner_a, owner_b, _, _ = two_owners
    token_hash_a, token_hash_b = "a" * 64, "b" * 64
    with migration_engine.begin() as connection:
        for owner_id, token_hash in ((owner_a, token_hash_a), (owner_b, token_hash_b)):
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(user_id, token_hash, auth_time, last_seen_at, expires_at) "
                    "VALUES (:user_id, :token_hash, now(), now(), now() + interval '1 hour')"
                ),
                {"user_id": owner_id, "token_hash": token_hash},
            )
    try:
        with auth_engine.connect() as connection, connection.begin():
            assert connection.scalar(text("SELECT count(*) FROM sessions")) == 0
            connection.execute(
                text("SELECT set_config('app.auth_session_hash', :hash, true)"),
                {"hash": token_hash_a},
            )
            assert connection.scalar(text("SELECT count(*) FROM sessions")) == 1
            assert connection.scalar(text("SELECT user_id FROM sessions")) == owner_a
    finally:
        with migration_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM sessions WHERE token_hash IN (:a, :b)"),
                {"a": token_hash_a, "b": token_hash_b},
            )
