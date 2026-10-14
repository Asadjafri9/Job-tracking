"""Consented provider routing with the PROVIDERS.md outcome state machine.

At most one normal attempt per ordered route plus one bounded short-429 retry
overall, inside a 60-second interactive deadline. Only consented, owner-scoped
credentials are unwrapped, held for the outbound call, and dropped.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.ai.contract import (
    DAILY_INTERACTIVE_OPERATIONS,
    DAILY_TOTAL_ATTEMPTS,
    INTERACTIVE_DEADLINE,
    MAX_PROVIDER_ATTEMPTS,
    OPERATION_OUTPUTS,
    OperationKind,
    catalog_model,
)
from app.ai.providers import DEFAULT_ADAPTERS, AttemptOutcome, ProviderAdapter
from app.config import get_settings
from app.db.idempotency import fingerprint
from app.db.models import (
    AiAttempt,
    AiOperation,
    ProviderCredential,
    ProviderRoute,
    ProviderSettings,
)
from app.security.credentials import CredentialUnavailable, unwrap_credential
from app.security.key_encryption import KeyEncryptionProvider

Purpose = Literal["INTERACTIVE", "BACKGROUND"]
SHORT_429_RETRY_CAP = 10.0


class RoutingError(Exception):
    """Caller-facing routing failure (consent, quota, idempotency conflicts)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class OperationResult:
    operation_id: UUID
    state: str
    outcome: str
    content: dict[str, Any] | None
    provider: str | None
    model: str | None
    replayed: bool


def _input_hmac_key() -> bytes:
    source = get_settings().app_hash_key or get_settings().oidc_client_secret or "local"
    return hashlib.sha256(source.encode() + b"\x00ai-operation-hmac").digest()


def _utc_day_start(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _check_daily_quotas(session: Session, owner_id: UUID, purpose: Purpose, now: datetime) -> None:
    day = _utc_day_start(now)
    if purpose == "INTERACTIVE":
        operations = int(
            session.scalar(
                select(func.count())
                .select_from(AiOperation)
                .where(AiOperation.user_id == owner_id, AiOperation.created_at >= day)
            )
            or 0
        )
        if operations >= DAILY_INTERACTIVE_OPERATIONS:
            raise RoutingError("quota_exceeded", "daily interactive operation limit reached")
    attempts = int(
        session.scalar(
            select(func.count())
            .select_from(AiAttempt)
            .where(AiAttempt.user_id == owner_id, AiAttempt.dispatched_at >= day)
        )
        or 0
    )
    if attempts >= DAILY_TOTAL_ATTEMPTS:
        raise RoutingError("quota_exceeded", "daily provider attempt limit reached")


def _consented_routes(
    session: Session, owner_id: UUID, purpose: Purpose
) -> list[tuple[ProviderRoute, ProviderCredential]]:
    settings = session.scalar(
        select(ProviderSettings).where(ProviderSettings.user_id == owner_id)
    )
    if settings is None:
        raise RoutingError("consent_required", "provider routing has not been configured")
    if purpose == "INTERACTIVE" and settings.interactive_consent_revision is None:
        raise RoutingError("consent_required", "interactive provider consent is required")
    if purpose == "BACKGROUND" and settings.background_consent_revision is None:
        raise RoutingError("consent_required", "background provider consent is required")
    rows = session.execute(
        select(ProviderRoute, ProviderCredential)
        .join(
            ProviderCredential,
            (ProviderCredential.user_id == ProviderRoute.user_id)
            & (ProviderCredential.id == ProviderRoute.credential_id),
        )
        .where(ProviderRoute.user_id == owner_id, ProviderRoute.enabled.is_(True))
        .order_by(ProviderRoute.position)
    ).all()
    eligible: list[tuple[ProviderRoute, ProviderCredential]] = []
    for route, credential in rows:
        if purpose == "INTERACTIVE":
            if not route.interactive_enabled or not credential.allow_interactive:
                continue
        else:
            if not route.background_enabled or not credential.allow_background:
                continue
        if not credential.enabled or credential.status == "REVOKED" or credential.revoked_at:
            continue
        if catalog_model(credential.provider, route.model_id) is None:
            continue
        eligible.append((route, credential))
    if not eligible:
        raise RoutingError("consent_required", "no enabled consented provider route")
    if len(eligible) > 1 and settings.fallback_consent_revision is None:
        raise RoutingError("consent_required", "fallback consent is required for ordered routes")
    return eligible


def run_operation(
    session: Session,
    *,
    owner_id: UUID,
    kind: OperationKind,
    request_payload: dict[str, Any],
    purpose: Purpose,
    idempotency_key: UUID,
    key_encryption: KeyEncryptionProvider,
    adapters: Mapping[str, ProviderAdapter] | None = None,
    profile_revision: int | None = None,
    context_revision: int | None = None,
    now: datetime | None = None,
) -> OperationResult:
    """Dispatch one owner operation through consented routes, or replay it."""
    moment = now or datetime.now(UTC)
    input_hmac = fingerprint(
        _input_hmac_key(), {"kind": kind, "purpose": purpose, "payload": request_payload}
    )
    existing = session.scalar(
        select(AiOperation)
        .where(AiOperation.user_id == owner_id, AiOperation.idempotency_key == idempotency_key)
        .with_for_update()
    )
    if existing is not None:
        if not hmac.compare_digest(existing.input_hmac, input_hmac):
            raise RoutingError("idempotency_conflict", "operation key was reused with new input")
        last = session.scalars(
            select(AiAttempt)
            .where(AiAttempt.operation_id == existing.id)
            .order_by(AiAttempt.attempt_number.desc())
        ).first()
        return OperationResult(
            operation_id=existing.id,
            state=existing.state,
            outcome="replayed",
            content=None,
            provider=last.provider if last else None,
            model=last.model if last else None,
            replayed=True,
        )

    _check_daily_quotas(session, owner_id, purpose, moment)
    routes = _consented_routes(session, owner_id, purpose)
    operation = AiOperation(
        user_id=owner_id,
        kind=kind,
        input_hmac=input_hmac,
        idempotency_key=idempotency_key,
        profile_revision=profile_revision,
        context_revision=context_revision,
        state="RUNNING",
        expires_at=moment + timedelta(days=30),
    )
    session.add(operation)
    session.flush()

    active_adapters = adapters if adapters is not None else DEFAULT_ADAPTERS
    deadline = moment + INTERACTIVE_DEADLINE
    retry_used = False
    dispatch_index = 0
    last_error = "no providers attempted"
    queue = list(routes)
    while queue and dispatch_index < MAX_PROVIDER_ATTEMPTS:
        route, credential = queue.pop(0)
        remaining = (deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 1:
            last_error = "interactive deadline exceeded"
            break
        dispatch_index += 1
        attempt = AiAttempt(
            user_id=owner_id,
            operation_id=operation.id,
            attempt_number=dispatch_index,
            credential_id=credential.id,
            provider=credential.provider,
            model=route.model_id,
            state="DISPATCHED",
            dispatched_at=datetime.now(UTC),
        )
        session.add(attempt)
        session.flush()
        adapter = active_adapters.get(credential.provider)
        if adapter is None:
            outcome = AttemptOutcome(kind="BAD_INPUT", error="no adapter for provider")
        else:
            try:
                api_key = unwrap_credential(
                    session,
                    owner_id=owner_id,
                    credential_id=credential.id,
                    purpose=purpose.lower(),
                    key_encryption=key_encryption,
                )
            except CredentialUnavailable:
                api_key = ""
            if not api_key:
                outcome = AttemptOutcome(kind="INVALID_KEY", error="credential cannot be used")
            else:
                outcome = adapter.call(
                    kind=kind,
                    request=request_payload,
                    api_key=api_key,
                    model_id=route.model_id,
                    timeout_seconds=min(remaining, 55.0),
                )
        attempt.completed_at = datetime.now(UTC)
        attempt.input_tokens = outcome.input_tokens
        attempt.output_tokens = outcome.output_tokens
        attempt.redacted_error = outcome.error
        if outcome.kind == "SUCCESS":
            try:
                validated = OPERATION_OUTPUTS[kind].model_validate(outcome.content)
            except ValidationError:
                outcome = AttemptOutcome(
                    kind="UNKNOWN", error="provider output failed schema validation"
                )
            else:
                attempt.state = "SUCCEEDED"
                attempt.redacted_outcome = {"status": "success"}
                operation.state = "SUCCEEDED"
                operation.completed_at = attempt.completed_at
                session.flush()
                return OperationResult(
                    operation_id=operation.id,
                    state="SUCCEEDED",
                    outcome="success",
                    content=validated.model_dump(),
                    provider=credential.provider,
                    model=outcome.model or route.model_id,
                    replayed=False,
                )
        if outcome.kind == "INVALID_KEY":
            session.execute(
                update(ProviderCredential)
                .where(ProviderCredential.id == credential.id)
                .values(status="NEEDS_ATTENTION")
            )
            attempt.state = "FAILED"
            attempt.redacted_outcome = {"status": "invalid_key"}
            last_error = "provider credential was rejected"
            continue
        if outcome.kind == "RATE_LIMITED" and outcome.retriable_once and not retry_used:
            if (outcome.retry_after_seconds or 0) <= min(
                SHORT_429_RETRY_CAP, (deadline - datetime.now(UTC)).total_seconds() - 1
            ):
                retry_used = True
                queue.insert(0, (route, credential))
                attempt.state = "FAILED"
                attempt.redacted_outcome = {"status": "rate_limited_retrying"}
                continue
        if outcome.kind in {"EXHAUSTED", "RATE_LIMITED", "UNAVAILABLE"}:
            attempt.state = "FAILED"
            attempt.redacted_outcome = {"status": outcome.kind.lower()}
            last_error = outcome.error or outcome.kind.lower()
            continue
        if outcome.kind in {"BAD_INPUT", "REFUSAL"}:
            attempt.state = "FAILED"
            attempt.redacted_outcome = {"status": outcome.kind.lower()}
            operation.state = "FAILED"
            operation.completed_at = attempt.completed_at
            session.flush()
            raise RoutingError(
                outcome.kind.lower(),
                outcome.error or "the provider rejected the request input",
            )
        attempt.state = "UNKNOWN"
        attempt.redacted_outcome = {"status": "unknown"}
        operation.state = "UNKNOWN"
        operation.completed_at = attempt.completed_at
        session.flush()
        return OperationResult(
            operation_id=operation.id,
            state="UNKNOWN",
            outcome="unknown",
            content=None,
            provider=credential.provider,
            model=route.model_id,
            replayed=False,
        )

    operation.state = "FAILED"
    operation.completed_at = datetime.now(UTC)
    session.flush()
    raise RoutingError("providers_unavailable", last_error)
