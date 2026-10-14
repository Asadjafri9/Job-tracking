"""PostgreSQL-backed API checks for email drafts and send tracking (M4)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth
from app.db.connection import sqlalchemy_url
from app.db.models import EmailDraft, Profile, User
from app.main import app
from app.modules import emails as emails_module

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "M4 API tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("M4 API tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://m4-api.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{identity}@example.test",
                login_email_verified=True,
            )
        )
        session.flush()
        session.add(Profile(user_id=identity, current_revision=1))
    try:
        yield identity
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == identity))


@pytest.fixture
def client(owner_id: UUID, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    auth = AuthContext(user_id=owner_id, token="m4-token", auth_time=datetime.now(UTC))
    app.dependency_overrides[require_auth] = lambda: auth
    monkeypatch.setattr(emails_module, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(emails_module, "require_csrf", lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _draft(client: TestClient, **overrides) -> dict:
    payload = {
        "recipient_email": "hiring@example.test",
        "employer": "Example Corp",
        "role": "Backend Engineer",
        "job_description": "Build Python services.",
    }
    payload.update(overrides)
    response = client.post("/api/v1/email-drafts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _reviewed(client: TestClient, draft: dict) -> dict:
    response = client.patch(
        f"/api/v1/email-drafts/{draft['id']}",
        json={"subject": "Applying for Backend Engineer", "body": "Dear team,\n\n..."},
        headers={"If-Match": f'"{draft["revision"]}"'},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_recipient_validation_rejects_injection(client: TestClient) -> None:
    bad = client.post(
        "/api/v1/email-drafts",
        json={
            "recipient_email": "a@b.test\r\nBcc: x@y.test",
            "employer": "E",
            "role": "R",
        },
    )
    assert bad.status_code == 422
    invalid = client.post(
        "/api/v1/email-drafts",
        json={"recipient_email": "not-an-email", "employer": "E", "role": "R"},
    )
    assert invalid.status_code == 422
    ok = _draft(client)
    assert ok["state"] == "DRAFT"


def test_edit_requires_revision_and_preserves_history(client: TestClient) -> None:
    draft = _draft(client)
    missing = client.patch(
        f"/api/v1/email-drafts/{draft['id']}", json={"subject": "Hi"}
    )
    assert missing.status_code == 428
    stale = client.patch(
        f"/api/v1/email-drafts/{draft['id']}",
        json={"subject": "Hi"},
        headers={"If-Match": '"99"'},
    )
    assert stale.status_code == 409
    reviewed = _reviewed(client, draft)
    assert reviewed["state"] == "READY_FOR_REVIEW"
    assert reviewed["revision"] == draft["revision"] + 1


def test_compose_opened_is_not_sent(client: TestClient) -> None:
    draft = _reviewed(client, _draft(client))
    opened = client.post(
        f"/api/v1/email-drafts/{draft['id']}/compose-opened",
        json={"event_idempotency_key": str(uuid4())},
    )
    assert opened.status_code == 200
    assert opened.json()["state"] == "COMPOSE_OPENED"
    applications = client.get("/api/v1/applications").json()["applications"]
    assert applications == []  # opening compose never creates an application


def test_confirm_sent_creates_one_email_application_and_replays(
    client: TestClient,
) -> None:
    draft = _reviewed(client, _draft(client))
    confirmed = client.post(
        f"/api/v1/email-drafts/{draft['id']}/confirm-sent",
        json={"sent_date": "2026-10-14", "event_idempotency_key": str(uuid4())},
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["status"] == "APPLIED"
    assert result["replayed"] is False

    again = client.post(
        f"/api/v1/email-drafts/{draft['id']}/confirm-sent",
        json={"sent_date": "2026-10-14", "event_idempotency_key": str(uuid4())},
    )
    assert again.json()["replayed"] is True

    applications = client.get("/api/v1/applications").json()["applications"]
    assert len(applications) == 1
    assert applications[0]["channel"] == "EMAIL"
    assert applications[0]["status"] == "APPLIED"

    detail = client.get(f"/api/v1/applications/{result['application_id']}").json()
    snapshot = detail["context_snapshot"]
    assert snapshot["draft_revision"] == draft["revision"]
    assert snapshot["subject"] == draft["subject"]
    assert snapshot["recipient_email"] == "hiring@example.test"
    assert detail["status_events"][0]["evidence_snapshot"]["kind"] == "USER_CONFIRMED_EMAIL"


def test_sent_draft_is_locked_and_stays_one_application(
    client: TestClient,
) -> None:
    draft = _reviewed(client, _draft(client))
    first = client.post(
        f"/api/v1/email-drafts/{draft['id']}/confirm-sent",
        json={"sent_date": "2026-10-10", "event_idempotency_key": str(uuid4())},
    ).json()
    detail = client.get(f"/api/v1/email-drafts/{draft['id']}").json()
    assert detail["state"] == "USER_CONFIRMED_SENT"

    edit = client.patch(
        f"/api/v1/email-drafts/{draft['id']}",
        json={"subject": "Changed"},
        headers={"If-Match": f'"{detail["revision"]}"'},
    )
    assert edit.status_code == 409

    applications = client.get("/api/v1/applications").json()["applications"]
    assert len(applications) == 1
    assert applications[0]["id"] == first["application_id"]


def test_confirm_with_stale_revision_never_overwrites_snapshot(
    client: TestClient,
) -> None:
    """A sent confirmation records an immutable snapshot; a revision mismatch
    is rejected instead of silently rewriting the tracked application."""
    draft = _reviewed(client, _draft(client))
    confirmed = client.post(
        f"/api/v1/email-drafts/{draft['id']}/confirm-sent",
        json={"sent_date": "2026-10-14", "event_idempotency_key": str(uuid4())},
    )
    assert confirmed.status_code == 200, confirmed.text
    application_id = confirmed.json()["application_id"]
    original = client.get(f"/api/v1/applications/{application_id}").json()
    assert original["context_snapshot"]["draft_revision"] == draft["revision"]

    # Simulate the draft content changing after the send was recorded.
    with Session(migration_engine) as session, session.begin():
        row = session.get(EmailDraft, UUID(draft["id"]))
        assert row is not None
        row.revision += 1

    mismatched = client.post(
        f"/api/v1/email-drafts/{draft['id']}/confirm-sent",
        json={"sent_date": "2026-10-15", "event_idempotency_key": str(uuid4())},
    )
    assert mismatched.status_code == 409
    unchanged = client.get(f"/api/v1/applications/{application_id}").json()
    assert unchanged["context_snapshot"] == original["context_snapshot"]
    assert unchanged["applied_date"] == original["applied_date"]


def test_cancel_blocks_further_use(client: TestClient) -> None:
    draft = _draft(client)
    canceled = client.patch(
        f"/api/v1/email-drafts/{draft['id']}",
        json={"state": "CANCELED"},
        headers={"If-Match": f'"{draft["revision"]}"'},
    )
    assert canceled.json()["state"] == "CANCELED"
    edit = client.patch(
        f"/api/v1/email-drafts/{draft['id']}",
        json={"subject": "Hi"},
        headers={"If-Match": f'"{canceled.json()["revision"]}"'},
    )
    assert edit.status_code == 409
    opened = client.post(
        f"/api/v1/email-drafts/{draft['id']}/compose-opened",
        json={"event_idempotency_key": str(uuid4())},
    )
    assert opened.status_code == 409


def test_generate_requires_provider_consent(client: TestClient) -> None:
    draft = _draft(client)
    response = client.post(
        f"/api/v1/email-drafts/{draft['id']}/generate",
        json={"expected_revision": draft["revision"]},
    )
    assert response.status_code == 403  # consent gate; never a silent send
