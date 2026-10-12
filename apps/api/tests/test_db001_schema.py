"""PostgreSQL-backed schema checks for DB-001 (requires an opted-in local DB)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.connection import sqlalchemy_url

DATABASE_URL = os.getenv("DB001_DATABASE_URL")
if DATABASE_URL is None:
    pytest.skip("DB001_DATABASE_URL is not configured", allow_module_level=True)
if urlparse(DATABASE_URL).hostname not in {"localhost", "127.0.0.1", "::1"}:
    pytest.skip("DB-001 database tests are restricted to loopback", allow_module_level=True)

engine: Engine = create_engine(sqlalchemy_url(DATABASE_URL), pool_pre_ping=True)

EXPECTED_TABLES = {
    "ai_attempts",
    "ai_operations",
    "application_answers",
    "application_sessions",
    "application_status_events",
    "applications",
    "audit_events",
    "auth_transactions",
    "deletion_journal",
    "discovered_jobs",
    "document_extractions",
    "documents",
    "email_drafts",
    "email_draft_documents",
    "email_draft_events",
    "extension_grants",
    "idempotency_records",
    "jobs",
    "monitored_sources",
    "monitoring_runs",
    "notifications",
    "profile_fact_versions",
    "profile_facts",
    "profiles",
    "provider_credentials",
    "provider_routes",
    "provider_settings",
    "sessions",
    "submission_events",
    "users",
}


def test_migration_head_created_the_expected_schema() -> None:
    inspector = inspect(engine)
    assert EXPECTED_TABLES <= set(inspector.get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_schema_has_owner_scoped_foreign_keys_revision_checks_and_indexes() -> None:
    inspector = inspect(engine)
    fact_fks = inspector.get_foreign_keys("profile_facts")
    assert any(
        fk["constrained_columns"] == ["user_id", "profile_id"]
        and fk["referred_table"] == "profiles"
        and fk["referred_columns"] == ["user_id", "id"]
        for fk in fact_fks
    )
    document_checks = {item["name"] for item in inspector.get_check_constraints("documents")}
    assert "ck_documents_document_size_limit" in document_checks
    assert "ck_documents_positive_revision" in document_checks
    assert "uq_monitoring_runs_daily_source_date" in {
        item["name"] for item in inspector.get_indexes("monitoring_runs")
    }


def test_provider_schema_never_has_a_plaintext_api_key_column() -> None:
    columns = {item["name"] for item in inspect(engine).get_columns("provider_credentials")}
    assert {"ciphertext", "nonce", "wrapped_dek", "kek_version", "key_last4"} <= columns
    assert not {"api_key", "raw_key", "plaintext_key", "secret"} & columns


def test_synthetic_seed_is_idempotent() -> None:
    from app.db.seed import seed

    with engine.begin() as connection:
        seed(connection)
        seed(connection)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM users WHERE issuer = 'urn:local:synthetic-db-seed'")
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM profiles "
                    "WHERE user_id = 'b48b1673-12f0-4ac2-a791-7432e8edc001'"
                )
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM profile_fact_versions "
                    "WHERE source_type = 'MANUAL' "
                    "AND source_ref = 'synthetic seed input'"
                )
            )
            == 1
        )


def test_database_rejects_cross_owner_profile_fact_and_oversized_document() -> None:
    owner_a, owner_b, profile_a = uuid4(), uuid4(), uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                "VALUES (:id, 'urn:test', :subject, :directory_id, :email, true)"
            ),
            [
                {
                    "id": owner_a,
                    "subject": str(owner_a),
                    "directory_id": uuid4(),
                    "email": f"{owner_a}@example.test",
                },
                {
                    "id": owner_b,
                    "subject": str(owner_b),
                    "directory_id": uuid4(),
                    "email": f"{owner_b}@example.test",
                },
            ],
        )
        connection.execute(
            text("INSERT INTO profiles (id, user_id) VALUES (:id, :owner)"),
            {"id": profile_a, "owner": owner_a},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("""
                    INSERT INTO profile_facts (id, user_id, profile_id, fact_key, value_type, value)
                    VALUES (:id, :owner, :profile, 'cross_owner', 'TEXT', '"invalid"'::jsonb)
                """),
                {"id": uuid4(), "owner": owner_b, "profile": profile_a},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO documents "
                    "(user_id, document_type, storage_key, file_name, "
                    "media_type, size_bytes, sha256) "
                    "VALUES (:owner, 'RESUME', 'local/test', 'resume.pdf', "
                    "'application/pdf', 5242881, :sha)"
                ),
                {"owner": owner_a, "sha": "a" * 64},
            )
        transaction.rollback()


def test_provider_credentials_routes_are_owner_scoped_and_capped() -> None:
    owner_a, owner_b, owner_without_settings = uuid4(), uuid4(), uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        for owner in (owner_a, owner_b, owner_without_settings):
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                    "VALUES (:id, 'urn:test-provider', :subject, :directory_id, :email, true)"
                ),
                {
                    "id": owner,
                    "subject": str(owner),
                    "directory_id": uuid4(),
                    "email": f"{owner}@example.test",
                },
            )
        for owner in (owner_a, owner_b):
            connection.execute(
                text(
                    "INSERT INTO provider_settings "
                    "(user_id, interactive_consent_revision, fallback_consent_revision) "
                    "VALUES (:owner, 1, :fallback_revision)"
                ),
                {"owner": owner, "fallback_revision": 1 if owner == owner_a else None},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE provider_settings SET fallback_consent_revision=0 WHERE user_id=:owner"),
                {"owner": owner_a},
            )

        credential_ids: list[UUID] = []
        providers = ("OPENROUTER", "XAI", "GEMINI")
        for position, provider in enumerate(providers, start=1):
            credential_id = uuid4()
            credential_ids.append(credential_id)
            connection.execute(
                text(
                    "INSERT INTO provider_credentials "
                    "(id, user_id, provider, ciphertext, nonce, wrapped_dek, kek_version, "
                    "key_last4, allow_interactive) "
                    "VALUES (:id, :owner, :provider, :cipher, :nonce, :wrapped, 'test-kek-v1', "
                    "'1234', true)"
                ),
                {
                    "id": credential_id,
                    "owner": owner_a,
                    "provider": provider,
                    "cipher": b"ciphertext",
                    "nonce": b"nonce",
                    "wrapped": b"wrapped-dek",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO provider_routes "
                    "(user_id, credential_id, position, model_id) "
                    "VALUES (:owner, :credential, :position, :model)"
                ),
                {
                    "owner": owner_a,
                    "credential": credential_id,
                    "position": position,
                    "model": f"synthetic-{provider.lower()}",
                },
            )

        duplicate_provider_id = uuid4()
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO provider_credentials "
                    "(id, user_id, provider, ciphertext, nonce, wrapped_dek, "
                    "kek_version, key_last4) "
                    "VALUES (:id, :owner, 'OPENROUTER', :cipher, :nonce, "
                    ":wrapped, 'test-kek-v1', '5678')"
                ),
                {
                    "id": duplicate_provider_id,
                    "owner": owner_a,
                    "cipher": b"ciphertext-2",
                    "nonce": b"nonce-2",
                    "wrapped": b"wrapped-dek-2",
                },
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO provider_routes "
                    "(user_id, credential_id, position, model_id) "
                    "VALUES (:owner, :credential, 4, 'synthetic-fourth')"
                ),
                {"owner": owner_a, "credential": credential_ids[0]},
            )
        foreign_credential_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO provider_credentials "
                "(id, user_id, provider, ciphertext, nonce, wrapped_dek, "
                "kek_version, key_last4) "
                "VALUES (:id, :owner, 'OPENROUTER', :cipher, :nonce, "
                ":wrapped, 'test-kek-v1', '0000')"
            ),
            {
                "id": foreign_credential_id,
                "owner": owner_b,
                "cipher": b"ciphertext-b",
                "nonce": b"nonce-b",
                "wrapped": b"wrapped-dek-b",
            },
        )
        unconfigured_credential_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO provider_credentials "
                "(id, user_id, provider, ciphertext, nonce, wrapped_dek, "
                "kek_version, key_last4, allow_interactive) "
                "VALUES (:id, :owner, 'GEMINI', :cipher, :nonce, :wrapped, "
                "'test-kek-v1', '9999', true)"
            ),
            {
                "id": unconfigured_credential_id,
                "owner": owner_without_settings,
                "cipher": b"ciphertext-c",
                "nonce": b"nonce-c",
                "wrapped": b"wrapped-dek-c",
            },
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO provider_routes "
                    "(user_id, credential_id, position, model_id) "
                    "VALUES (:owner, :credential, 1, 'settings-required-model')"
                ),
                {"owner": owner_without_settings, "credential": unconfigured_credential_id},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO provider_routes "
                    "(user_id, credential_id, position, model_id) "
                    "VALUES (:owner, :credential, 1, 'no-consent-model')"
                ),
                {"owner": owner_b, "credential": foreign_credential_id},
            )
        connection.execute(
            text("UPDATE provider_credentials SET allow_interactive=true WHERE id=:id"),
            {"id": foreign_credential_id},
        )
        route_b = uuid4()
        connection.execute(
            text(
                "INSERT INTO provider_routes "
                "(id, user_id, credential_id, position, model_id) "
                "VALUES (:id, :owner, :credential, 1, 'consented-model')"
            ),
            {"id": route_b, "owner": owner_b, "credential": foreign_credential_id},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE provider_routes SET position=2 WHERE id=:id"), {"id": route_b}
            )
        connection.execute(
            text("UPDATE provider_settings SET fallback_consent_revision=1 WHERE user_id=:owner"),
            {"owner": owner_b},
        )
        connection.execute(
            text("UPDATE provider_routes SET position=2 WHERE id=:id"), {"id": route_b}
        )
        connection.execute(
            text("UPDATE provider_settings SET fallback_consent_revision=NULL WHERE user_id=:owner"),
            {"owner": owner_b},
        )
        assert (
            connection.scalar(
                text("SELECT enabled FROM provider_routes WHERE id=:id"), {"id": route_b}
            )
            is False
        )
        connection.execute(
            text("UPDATE provider_settings SET fallback_consent_revision=1 WHERE user_id=:owner"),
            {"owner": owner_b},
        )
        connection.execute(
            text("UPDATE provider_routes SET enabled=true WHERE id=:id"), {"id": route_b}
        )
        connection.execute(
            text("UPDATE provider_credentials SET allow_background=true WHERE id=:id"),
            {"id": foreign_credential_id},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE provider_routes SET background_enabled=true WHERE id=:id"),
                {"id": route_b},
            )
        connection.execute(
            text("UPDATE provider_settings SET background_consent_revision=1 WHERE user_id=:owner"),
            {"owner": owner_b},
        )
        connection.execute(
            text("UPDATE provider_routes SET background_enabled=true WHERE id=:id"),
            {"id": route_b},
        )
        connection.execute(
            text("UPDATE provider_credentials SET enabled=false WHERE id=:id"),
            {"id": foreign_credential_id},
        )
        assert (
            connection.scalar(
                text("SELECT enabled FROM provider_routes WHERE id=:id"), {"id": route_b}
            )
            is False
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO provider_routes "
                    "(user_id, credential_id, position, model_id) "
                    "VALUES (:owner, :credential, 1, 'foreign-model')"
                ),
                {"owner": owner_a, "credential": foreign_credential_id},
            )
        transaction.rollback()


def test_email_document_join_enforces_owner_and_preserves_application_snapshot() -> None:
    owner_a, owner_b, draft_id, document_a, document_b = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        for owner in (owner_a, owner_b):
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                    "VALUES (:id, 'urn:test-mail', :subject, :directory_id, :email, true)"
                ),
                {
                    "id": owner,
                    "subject": str(owner),
                    "directory_id": uuid4(),
                    "email": f"{owner}@example.test",
                },
            )
        connection.execute(
            text(
                "INSERT INTO email_drafts "
                "(id, user_id, recipient_email, employer, role, subject, body) "
                "VALUES (:id, :owner, 'jobs@example.test', 'Example', 'Designer', 'Hello', 'Draft')"
            ),
            {"id": draft_id, "owner": owner_a},
        )
        for owner, document_id in ((owner_a, document_a), (owner_b, document_b)):
            connection.execute(
                text(
                    "INSERT INTO documents "
                    "(id, user_id, document_type, storage_key, file_name, "
                    "media_type, size_bytes, sha256) "
                    "VALUES (:id, :owner, 'RESUME', :storage, 'resume.pdf', "
                    "'application/pdf', 10, :sha)"
                ),
                {
                    "id": document_id,
                    "owner": owner,
                    "storage": f"synthetic/{document_id}",
                    "sha": "b" * 64,
                },
            )
        connection.execute(
            text(
                "INSERT INTO email_draft_documents "
                "(user_id, email_draft_id, document_id, document_revision, position) "
                "VALUES (:owner, :draft, :document, 1, 1)"
            ),
            {"owner": owner_a, "draft": draft_id, "document": document_a},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO email_draft_documents "
                    "(user_id, email_draft_id, document_id, document_revision, position) "
                    "VALUES (:owner, :draft, :document, 1, 2)"
                ),
                {"owner": owner_a, "draft": draft_id, "document": document_b},
            )
        application_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO applications "
                "(id, user_id, channel, employer, role, document_metadata_snapshot) "
                "VALUES (:id, :owner, 'MANUAL', 'Example', 'Designer', "
                "CAST(:snapshot AS jsonb))"
            ),
            {
                "id": application_id,
                "owner": owner_a,
                "snapshot": json.dumps([{"name": "resume.pdf", "revision": 1}]),
            },
        )
        connection.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document_a})
        assert (
            connection.scalar(
                text("SELECT count(*) FROM email_draft_documents WHERE document_id = :id"),
                {"id": document_a},
            )
            == 0
        )
        assert (
            connection.scalar(
                text(
                    "SELECT jsonb_array_length(document_metadata_snapshot) "
                    "FROM applications WHERE id = :id"
                ),
                {"id": application_id},
            )
            == 1
        )
        transaction.rollback()


def test_database_enforces_json_cardinality_and_size_limits() -> None:
    owner_id, document_id = uuid4(), uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                "VALUES (:id, 'urn:test-json', :subject, :directory_id, :email, true)"
            ),
            {
                "id": owner_id,
                "subject": str(owner_id),
                "directory_id": uuid4(),
                "email": f"{owner_id}@example.test",
            },
        )
        connection.execute(
            text(
                "INSERT INTO documents "
                "(id, user_id, document_type, storage_key, file_name, "
                "media_type, size_bytes, sha256) "
                "VALUES (:id, :owner, 'RESUME', 'synthetic/json.pdf', 'json.pdf', "
                "'application/pdf', 10, :sha)"
            ),
            {"id": document_id, "owner": owner_id, "sha": "c" * 64},
        )
        invalid_extraction_inputs = [
            {"candidates": json.dumps([{}] * 201), "anchors": "[]", "count": 201},
            {"candidates": json.dumps([{"x": "c" * 1_100_000}]), "anchors": "[]", "count": 1},
            {"candidates": "[]", "anchors": json.dumps([{}] * 201), "count": 0},
            {"candidates": "[]", "anchors": json.dumps([{"x": "a" * 270_000}]), "count": 0},
        ]
        for payload in invalid_extraction_inputs:
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO document_extractions "
                        "(user_id, document_id, document_revision, parse_version, candidates, "
                        "source_anchors, candidate_count) VALUES (:owner, :document, 1, 'test', "
                        "CAST(:candidates AS jsonb), CAST(:anchors AS jsonb), :count)"
                    ),
                    {"owner": owner_id, "document": document_id, **payload},
                )

        valid_session_base = (
            "INSERT INTO application_sessions "
            "(user_id, profile_revision, context_revision, selected_fact_versions, "
            "selected_document_versions) VALUES (:owner, 1, 1, CAST(:facts AS jsonb), "
            "CAST(:documents AS jsonb))"
        )
        invalid_session_inputs = [
            {"facts": json.dumps([{}] * 41), "documents": "[]"},
            {"facts": json.dumps([{"x": "f" * 2_000}] * 40), "documents": "[]"},
            {"facts": "[]", "documents": json.dumps([{}] * 11)},
            {"facts": "[]", "documents": json.dumps([{"x": "d" * 4_000}] * 10)},
        ]
        for payload in invalid_session_inputs:
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text(valid_session_base), {"owner": owner_id, **payload})
        transaction.rollback()


def test_confirmed_fact_timestamp_source_consent_native_identity_and_email_events() -> None:
    owner_id, profile_id, source_id, fact_id, draft_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, issuer, subject, directory_object_id, login_email, login_email_verified) "
                "VALUES (:id, 'urn:test-contracts', :subject, :directory_id, :email, true)"
            ),
            {
                "id": owner_id,
                "subject": str(owner_id),
                "directory_id": uuid4(),
                "email": f"{owner_id}@example.test",
            },
        )
        connection.execute(
            text("INSERT INTO profiles (id, user_id) VALUES (:id, :owner)"),
            {"id": profile_id, "owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO profile_facts "
                "(id, user_id, profile_id, fact_key, value_type, value) "
                "VALUES (:id, :owner, :profile, 'role', 'TEXT', CAST(:value AS jsonb))"
            ),
            {
                "id": fact_id,
                "owner": owner_id,
                "profile": profile_id,
                "value": json.dumps("Designer"),
            },
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO profile_fact_versions "
                    "(user_id, profile_fact_id, revision, value, source_type, confirmation_state) "
                    "VALUES (:owner, :fact, 1, CAST(:value AS jsonb), 'MANUAL', 'CONFIRMED')"
                ),
                {"owner": owner_id, "fact": fact_id, "value": json.dumps("Designer")},
            )

        connection.execute(
            text(
                "INSERT INTO monitored_sources "
                "(id, user_id, public_url, source_kind, timezone) "
                "VALUES (:id, :owner, 'https://example.test/careers', 'HTML', 'UTC')"
            ),
            {"id": source_id, "owner": owner_id},
        )
        assert (
            connection.scalar(
                text("SELECT state FROM monitored_sources WHERE id = :id"), {"id": source_id}
            )
            == "PAUSED"
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO monitored_sources "
                    "(user_id, public_url, source_kind, state, schedule, timezone, next_run_at) "
                    "VALUES (:owner, 'https://example.test/active', 'HTML', 'ACTIVE', 'DAILY', "
                    "'UTC', now())"
                ),
                {"owner": owner_id},
            )
        connection.execute(
            text(
                "UPDATE monitored_sources SET state='ACTIVE', next_run_at=now(), "
                "scheduled_check_consented_at=now(), consent_revision=1 WHERE id=:id"
            ),
            {"id": source_id},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO discovered_jobs "
                    "(user_id, source_id, native_id, title) "
                    "VALUES (:owner, :source, 'native-1', 'Designer')"
                ),
                {"owner": owner_id, "source": source_id},
            )
        connection.execute(
            text(
                "INSERT INTO discovered_jobs "
                "(user_id, source_id, native_id_namespace, native_id, title) "
                "VALUES (:owner, :source, 'synthetic-feed', 'native-1', 'Designer')"
            ),
            {"owner": owner_id, "source": source_id},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO discovered_jobs "
                    "(user_id, source_id, native_id_namespace, native_id, title) "
                    "VALUES (:owner, :source, 'synthetic-feed', 'native-1', 'Designer duplicate')"
                ),
                {"owner": owner_id, "source": source_id},
            )

        connection.execute(
            text(
                "INSERT INTO email_drafts "
                "(id, user_id, recipient_email, employer, role, subject, body) "
                "VALUES (:id, :owner, 'jobs@example.test', 'Example', 'Designer', 'Hello', 'Draft')"
            ),
            {"id": draft_id, "owner": owner_id},
        )
        event_key = uuid4()
        event_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO email_draft_events "
                "(id, user_id, email_draft_id, event_idempotency_key, event_type, "
                "draft_revision, occurred_at) "
                "VALUES (:id, :owner, :draft, :key, 'COMPOSE_OPENED', 1, :occurred)"
            ),
            {
                "id": event_id,
                "owner": owner_id,
                "draft": draft_id,
                "key": event_key,
                "occurred": datetime.now(UTC),
            },
        )
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                text("UPDATE email_draft_events SET event_type='USER_CONFIRMED_SENT' WHERE id=:id"),
                {"id": event_id},
            )
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                text("DELETE FROM email_draft_events WHERE id=:id"),
                {"id": event_id},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO email_draft_events "
                    "(user_id, email_draft_id, event_idempotency_key, event_type, "
                    "draft_revision, occurred_at) "
                    "VALUES (:owner, :draft, :key, 'USER_CONFIRMED_SENT', 1, now())"
                ),
                {"owner": owner_id, "draft": draft_id, "key": event_key},
            )
        transaction.rollback()
