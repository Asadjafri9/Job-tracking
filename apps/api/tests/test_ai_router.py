"""PostgreSQL checks for the consented AI fallback router (AI-003)."""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ai.contract import ExtractionInput
from app.ai.providers import AttemptOutcome
from app.ai.router import RoutingError, run_operation
from app.config import LOCAL_TEST_KEK
from app.db.connection import sqlalchemy_url
from app.db.models import (
    AiAttempt,
    AiOperation,
    Profile,
    ProviderCredential,
    ProviderRoute,
    ProviderSettings,
    User,
)
from app.db.tenant import tenant_session
from app.security.credentials import store_credential
from app.security.key_encryption import LocalAesGcmKeyEncryption

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "AI router tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("AI router tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)
KEK = LocalAesGcmKeyEncryption(base64.b64decode(LOCAL_TEST_KEK), "local-test-v1")

EXTRACTION_PAYLOAD = ExtractionInput(
    document_type="RESUME",
    sections=[{"section_id": 0, "anchor": {}, "text": "Worked at Example Corp."}],
).model_dump()


class FakeAdapter:
    def __init__(self, provider: str, outcomes: list[AttemptOutcome]) -> None:
        self.provider = provider
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> AttemptOutcome:
        self.calls.append(kwargs)
        return self._outcomes.pop(0) if self._outcomes else AttemptOutcome(kind="UNAVAILABLE")


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://ai-router.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{identity}@example.test",
                login_email_verified=True,
            )
        )
        session.flush()
        session.add(Profile(user_id=identity))
    try:
        yield identity
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == identity))


def _save_key(
    owner: UUID, provider: str, *, interactive: bool = True, background: bool = False
) -> UUID:
    with tenant_session(runtime_engine, owner) as session:
        summary = store_credential(
            session,
            owner_id=owner,
            provider=provider,
            api_key=f"{provider.lower()}-secret-key",
            key_encryption=KEK,
            allow_interactive=interactive,
            allow_background=background,
        )
        return summary.id


def _settings_routes(
    owner: UUID,
    routes: list[tuple[UUID, str]],
    *,
    interactive: bool = True,
    fallback: bool = True,
    background: bool = False,
) -> None:
    with tenant_session(runtime_engine, owner) as session:
        settings = ProviderSettings(
            user_id=owner,
            revision=1,
            interactive_consent_revision=1 if interactive else None,
            fallback_consent_revision=1 if fallback else None,
            background_consent_revision=1 if background else None,
        )
        session.add(settings)
        session.flush()
        for position, (credential_id, model) in enumerate(routes, start=1):
            session.add(
                ProviderRoute(
                    user_id=owner,
                    credential_id=credential_id,
                    position=position,
                    model_id=model,
                    enabled=True,
                    interactive_enabled=interactive,
                    background_enabled=background,
                )
            )


def _attempts(owner: UUID) -> list[AiAttempt]:
    with Session(migration_engine) as session:
        return list(
            session.scalars(
                select(AiAttempt)
                .where(AiAttempt.user_id == owner)
                .order_by(AiAttempt.attempt_number)
            ).all()
        )


def _operations(owner: UUID) -> list[AiOperation]:
    with Session(migration_engine) as session:
        return list(
            session.scalars(select(AiOperation).where(AiOperation.user_id == owner)).all()
        )


def test_successful_first_route_returns_validated_content(owner_id: UUID) -> None:
    credential_id = _save_key(owner_id, "OPENROUTER")
    _settings_routes(owner_id, [(credential_id, "deepseek/deepseek-v4-flash")])
    adapter = FakeAdapter(
        "OPENROUTER",
        [AttemptOutcome(kind="SUCCESS", content={"candidates": []}, model="deepseek")],
    )
    with tenant_session(runtime_engine, owner_id) as session:
        result = run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters={"OPENROUTER": adapter},
        )
    assert result.state == "SUCCEEDED"
    assert result.content == {"candidates": []}
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["api_key"] == "openrouter-secret-key"
    attempts = _attempts(owner_id)
    assert len(attempts) == 1 and attempts[0].state == "SUCCEEDED"


def test_invalid_key_marks_credential_and_falls_through(owner_id: UUID) -> None:
    first = _save_key(owner_id, "OPENROUTER")
    second = _save_key(owner_id, "XAI")
    _settings_routes(
        owner_id, [(first, "deepseek/deepseek-v4-flash"), (second, "grok-4.7")]
    )
    adapters = {
        "OPENROUTER": FakeAdapter("OPENROUTER", [AttemptOutcome(kind="INVALID_KEY")]),
        "XAI": FakeAdapter("XAI", [AttemptOutcome(kind="SUCCESS", content={"candidates": []})]),
    }
    with tenant_session(runtime_engine, owner_id) as session:
        result = run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters=adapters,
        )
    assert result.state == "SUCCEEDED" and result.provider == "XAI"
    with Session(migration_engine) as session:
        credential = session.get(ProviderCredential, first)
        assert credential is not None and credential.status == "NEEDS_ATTENTION"
    assert [attempt.state for attempt in _attempts(owner_id)] == ["FAILED", "SUCCEEDED"]


def test_unknown_outcome_stops_without_fallback(owner_id: UUID) -> None:
    first = _save_key(owner_id, "OPENROUTER")
    second = _save_key(owner_id, "XAI")
    _settings_routes(
        owner_id, [(first, "deepseek/deepseek-v4-flash"), (second, "grok-4.7")]
    )
    adapters = {
        "OPENROUTER": FakeAdapter("OPENROUTER", [AttemptOutcome(kind="UNKNOWN")]),
        "XAI": FakeAdapter("XAI", [AttemptOutcome(kind="SUCCESS", content={"candidates": []})]),
    }
    with tenant_session(runtime_engine, owner_id) as session:
        result = run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters=adapters,
        )
    assert result.state == "UNKNOWN"
    assert adapters["XAI"].calls == []


def test_bad_input_does_not_charge_other_providers(owner_id: UUID) -> None:
    first = _save_key(owner_id, "OPENROUTER")
    second = _save_key(owner_id, "XAI")
    _settings_routes(
        owner_id, [(first, "deepseek/deepseek-v4-flash"), (second, "grok-4.7")]
    )
    adapters = {
        "OPENROUTER": FakeAdapter("OPENROUTER", [AttemptOutcome(kind="BAD_INPUT")]),
        "XAI": FakeAdapter("XAI", [AttemptOutcome(kind="SUCCESS", content={"candidates": []})]),
    }
    with (
        tenant_session(runtime_engine, owner_id) as session,
        pytest.raises(RoutingError, match="provider rejected the request input"),
    ):
        run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters=adapters,
        )
    assert adapters["XAI"].calls == []


def test_exhausted_routes_raise_providers_unavailable(owner_id: UUID) -> None:
    first = _save_key(owner_id, "OPENROUTER")
    _settings_routes(owner_id, [(first, "deepseek/deepseek-v4-flash")])
    adapters = {"OPENROUTER": FakeAdapter("OPENROUTER", [AttemptOutcome(kind="EXHAUSTED")])}
    with (
        tenant_session(runtime_engine, owner_id) as session,
        pytest.raises(RoutingError) as error,
    ):
        run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters=adapters,
        )
    assert error.value.code == "providers_unavailable"


def test_idempotent_replay_does_not_redispatch(owner_id: UUID) -> None:
    credential_id = _save_key(owner_id, "OPENROUTER")
    _settings_routes(owner_id, [(credential_id, "deepseek/deepseek-v4-flash")])
    adapter = FakeAdapter(
        "OPENROUTER", [AttemptOutcome(kind="SUCCESS", content={"candidates": []})]
    )
    key = uuid4()
    with tenant_session(runtime_engine, owner_id) as session:
        first = run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=key,
            key_encryption=KEK,
            adapters={"OPENROUTER": adapter},
        )
        replay = run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=key,
            key_encryption=KEK,
            adapters={"OPENROUTER": adapter},
        )
    assert replay.replayed is True and replay.operation_id == first.operation_id
    assert len(adapter.calls) == 1
    assert len(_operations(owner_id)) == 1


def test_no_consent_blocks_dispatch(owner_id: UUID) -> None:
    credential_id = _save_key(owner_id, "OPENROUTER", background=True)
    _settings_routes(
        owner_id,
        [(credential_id, "deepseek/deepseek-v4-flash")],
        interactive=False,
        background=True,
    )
    with (
        tenant_session(runtime_engine, owner_id) as session,
        pytest.raises(RoutingError) as error,
    ):
        run_operation(
            session,
            owner_id=owner_id,
            kind="EXTRACTION",
            request_payload=EXTRACTION_PAYLOAD,
            purpose="INTERACTIVE",
            idempotency_key=uuid4(),
            key_encryption=KEK,
            adapters={},
        )
    assert error.value.code == "consent_required"


def test_attempt_ceiling_blocks_new_dispatch(owner_id: UUID) -> None:
    credential_id = _save_key(owner_id, "OPENROUTER")
    _settings_routes(owner_id, [(credential_id, "deepseek/deepseek-v4-flash")])
    with tenant_session(runtime_engine, owner_id) as session:
        for op_index in range(50):
            operation = AiOperation(
                user_id=owner_id,
                kind="EXTRACTION",
                input_hmac=f"{op_index:064x}",
                idempotency_key=uuid4(),
                state="SUCCEEDED",
            )
            session.add(operation)
            session.flush()
            for attempt_number in range(1, 4):
                session.add(
                    AiAttempt(
                        user_id=owner_id,
                        operation_id=operation.id,
                        attempt_number=attempt_number,
                        credential_id=credential_id,
                        provider="OPENROUTER",
                        model="deepseek/deepseek-v4-flash",
                        state="FAILED",
                        dispatched_at=datetime.now(UTC) - timedelta(minutes=1),
                    )
                )
        session.flush()
        with pytest.raises(RoutingError) as error:
            run_operation(
                session,
                owner_id=owner_id,
                kind="EXTRACTION",
                request_payload=EXTRACTION_PAYLOAD,
                purpose="INTERACTIVE",
                idempotency_key=uuid4(),
                key_encryption=KEK,
                adapters={},
            )
        assert error.value.code == "quota_exceeded"
