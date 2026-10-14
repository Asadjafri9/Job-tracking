"""PostgreSQL-backed API checks for application sessions and tracking (M3)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.routes import AuthContext, require_auth
from app.db.connection import sqlalchemy_url
from app.db.models import (
    ApplicationSession,
    Profile,
    ProfileFact,
    ProfileFactVersion,
    User,
)
from app.main import app
from app.modules import applications as applications_module

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "M3 API tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("M3 API tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://m3-api.local.test/issuer",
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
    auth = AuthContext(user_id=owner_id, token="m3-token", auth_time=datetime.now(UTC))
    app.dependency_overrides[require_auth] = lambda: auth
    monkeypatch.setattr(applications_module, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(applications_module, "require_csrf", lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _fact(owner_id: UUID, key: str, value: str, purposes: list[str]) -> tuple[UUID, int]:
    with Session(migration_engine) as session, session.begin():
        profile = session.scalar(select(Profile).where(Profile.user_id == owner_id))
        fact = ProfileFact(
            user_id=owner_id,
            profile_id=profile.id,
            fact_key=key,
            value_type="TEXT",
            value=value,
            sensitivity="NORMAL",
            allowed_purposes=purposes,
            current_revision=1,
            is_active=True,
        )
        session.add(fact)
        session.flush()
        session.add(
            ProfileFactVersion(
                user_id=owner_id,
                profile_fact_id=fact.id,
                revision=1,
                value=value,
                source_type="MANUAL",
                confirmation_state="CONFIRMED",
                confirmed_at=datetime.now(UTC),
            )
        )
        return fact.id, 1


def _session(client: TestClient, **overrides) -> dict:
    payload = {
        "employer": "Example Corp",
        "role": "Backend Engineer",
        "raw_job_url": "https://jobs.example.test/post/1?utm_source=x&ref=y",
        "job_context": {"excerpt": "Python services"},
    }
    payload.update(overrides)
    response = client.post("/api/v1/application-sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_session_create_and_url_canonicalization(client: TestClient) -> None:
    body = _session(client)
    assert body["state"] == "PREPARED"
    assert body["canonical_job_url"] == "https://jobs.example.test/post/1?ref=y"
    assert body["draft_answers"] is None
    listing = client.get("/api/v1/application-sessions")
    assert listing.json()["sessions"][0]["id"] == body["id"]


def test_session_requires_https_for_remote_hosts(client: TestClient) -> None:
    response = client.post(
        "/api/v1/application-sessions",
        json={"raw_job_url": "http://jobs.example.test/post/1"},
    )
    assert response.status_code == 422


def test_session_fact_snapshot_validates_revision(
    client: TestClient, owner_id: UUID
) -> None:
    fact_id, revision = _fact(owner_id, "contact.email", "a@b.test", ["AUTOFILL"])
    body = _session(
        client, selected_fact_versions=[{"fact_id": str(fact_id), "revision": revision}]
    )
    assert body["selected_fact_versions"][0]["fact_key"] == "contact.email"
    stale = client.post(
        "/api/v1/application-sessions",
        json={"selected_fact_versions": [{"fact_id": str(fact_id), "revision": 99}]},
    )
    assert stale.status_code == 409


def test_draft_answers_requires_consent_and_returns_403(
    client: TestClient, owner_id: UUID
) -> None:
    body = _session(client)
    response = client.post(
        f"/api/v1/application-sessions/{body['id']}/draft-answers",
        json={
            "questions": [
                {
                    "field_id": "q1",
                    "label": "Why us?",
                    "field_type": "TEXTAREA",
                    "options": [],
                    "required": True,
                    "sensitive": False,
                }
            ],
            "expected_profile_revision": 1,
        },
    )
    # No provider routes/consent configured -> consent gate, never silent.
    assert response.status_code == 403


def test_submit_click_creates_one_application_and_replays(
    client: TestClient,
) -> None:
    body = _session(client)
    key = uuid4()
    event = {
        "event_idempotency_key": str(key),
        "application_session_id": body["id"],
        "evidence_type": "SUBMIT_CLICK",
        "evidence_source": "USER_GESTURE",
        "observed_at": datetime.now(UTC).isoformat(),
        "gesture_ref_hash": "a" * 64,
        "evidence": {},
    }
    first = client.post("/api/v1/submission-events", json=event)
    assert first.status_code == 201, first.text
    assert first.json()["replayed"] is False
    application_id = first.json()["application_id"]
    assert application_id is not None

    replay = client.post("/api/v1/submission-events", json=event)
    assert replay.json()["replayed"] is True

    applications = client.get("/api/v1/applications")
    rows = applications.json()["applications"]
    assert len(rows) == 1
    assert rows[0]["status"] == "SUBMISSION_ATTEMPTED"  # a click is not APPLIED
    assert rows[0]["channel"] == "WEB_FORM"

    detail = client.get(f"/api/v1/applications/{application_id}").json()
    assert detail["status_events"][0]["new_status"] == "SUBMISSION_ATTEMPTED"
    assert detail["submission_events"][0]["evidence_type"] == "SUBMIT_CLICK"

    session_view = client.get(f"/api/v1/application-sessions/{body['id']}").json()
    assert session_view["state"] == "SUBMISSION_ATTEMPTED"
    assert session_view["application_id"] == application_id


def test_applied_answers_revision_binding_and_snapshot(client: TestClient) -> None:
    body = _session(client)
    stale = client.post(
        f"/api/v1/application-sessions/{body['id']}/applied-answers",
        json={"entries": [], "expected_context_revision": 99},
    )
    assert stale.status_code == 409

    reported = client.post(
        f"/api/v1/application-sessions/{body['id']}/applied-answers",
        json={
            "entries": [
                {"field_id": "q1", "value": "Three years", "status": "filled"},
                {"field_id": "q2", "value": None, "status": "skipped"},
            ],
            "expected_context_revision": body["context_revision"],
        },
    )
    assert reported.status_code == 200, reported.text

    click = client.post(
        "/api/v1/submission-events",
        json={
            "event_idempotency_key": str(uuid4()),
            "application_session_id": body["id"],
            "evidence_type": "SUBMIT_CLICK",
            "evidence_source": "USER_GESTURE",
            "observed_at": datetime.now(UTC).isoformat(),
            "gesture_ref_hash": "f" * 64,
            "evidence": {},
        },
    )
    detail = client.get(
        f"/api/v1/applications/{click.json()['application_id']}"
    ).json()
    assert len(detail["answers"]) == 2
    by_field = {row["field_key"]: row for row in detail["answers"]}
    assert by_field["q1"]["answer_value"]["value"] == "Three years"
    assert by_field["q1"]["answer_value"]["status"] == "filled"
    assert by_field["q2"]["answer_value"]["status"] == "skipped"


def test_validation_blocked_never_advances_status(client: TestClient) -> None:
    body = _session(client)
    click = client.post(
        "/api/v1/submission-events",
        json={
            "event_idempotency_key": str(uuid4()),
            "application_session_id": body["id"],
            "evidence_type": "SUBMIT_CLICK",
            "evidence_source": "USER_GESTURE",
            "observed_at": datetime.now(UTC).isoformat(),
            "gesture_ref_hash": "b" * 64,
            "evidence": {},
        },
    )
    assert click.status_code == 201
    blocked = client.post(
        "/api/v1/submission-events",
        json={
            "event_idempotency_key": str(uuid4()),
            "application_session_id": body["id"],
            "evidence_type": "VALIDATION_BLOCKED",
            "evidence_source": "CONTENT_OBSERVER",
            "observed_at": datetime.now(UTC).isoformat(),
            "gesture_ref_hash": "c" * 64,
            "signal_code": "REQUIRED_FIELD",
            "evidence": {},
        },
    )
    assert blocked.status_code == 201
    applications = client.get("/api/v1/applications").json()["applications"]
    assert applications[0]["status"] == "SUBMISSION_ATTEMPTED"


def test_stale_or_future_observation_rejected(client: TestClient) -> None:
    body = _session(client)
    for observed in (
        datetime.now(UTC) - timedelta(hours=25),
        datetime.now(UTC) + timedelta(hours=1),
    ):
        response = client.post(
            "/api/v1/submission-events",
            json={
                "event_idempotency_key": str(uuid4()),
                "application_session_id": body["id"],
                "evidence_type": "SUBMIT_CLICK",
                "evidence_source": "USER_GESTURE",
                "observed_at": observed.isoformat(),
                "gesture_ref_hash": "d" * 64,
                "evidence": {},
            },
        )
        assert response.status_code == 422


def test_manual_application_and_confirm_applied_flow(client: TestClient) -> None:
    created = client.post(
        "/api/v1/applications",
        json={
            "employer": "Manual Co",
            "role": "SRE",
            "raw_job_url": "https://manual.example.test/j/9",
        },
    )
    assert created.status_code == 201
    application = created.json()
    assert application["status"] == "SUBMISSION_ATTEMPTED"
    revision = application["revision"]

    conflict = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"status": "NEEDS_FOLLOW_UP"},
        headers={"If-Match": '"999"'},
    )
    assert conflict.status_code == 409

    patched = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"status": "NEEDS_FOLLOW_UP", "follow_up_date": "2026-10-20"},
        headers={"If-Match": f'"{revision}"'},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "NEEDS_FOLLOW_UP"

    missing_date = client.post(
        f"/api/v1/applications/{application['id']}/confirm",
        json={},
        headers={"If-Match": f'"{revision + 1}"'},
    )
    assert missing_date.status_code == 422

    confirmed = client.post(
        f"/api/v1/applications/{application['id']}/confirm",
        json={"applied_date": "2026-10-14", "note": "site showed success"},
        headers={"If-Match": f'"{revision + 1}"'},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "APPLIED"
    assert confirmed.json()["applied_at"] is not None

    detail = client.get(f"/api/v1/applications/{application['id']}").json()
    sources = [event["source"] for event in detail["status_events"]]
    assert sources == ["USER_CONFIRMATION", "USER_CONFIRMATION", "USER_CONFIRMATION"]


def test_applied_without_date_rejected(client: TestClient) -> None:
    created = client.post(
        "/api/v1/applications", json={"employer": "X", "role": "Y", "status": "APPLIED"}
    )
    assert created.status_code == 422


def test_dashboard_counts_sessions_and_applications_separately(
    client: TestClient,
) -> None:
    _session(client)
    client.post("/api/v1/applications", json={"employer": "A", "role": "B"})
    dash = client.get("/api/v1/dashboard")
    assert dash.status_code == 200
    body = dash.json()
    assert body["prepared_sessions"] == 1
    assert body["applications_by_status"] == {"SUBMISSION_ATTEMPTED": 1}
    assert isinstance(body["recent_status_events"], list)


def test_expired_session_is_not_open_and_does_not_block_creation(
    client: TestClient, owner_id: UUID
) -> None:
    body = _session(client)
    with Session(migration_engine) as session, session.begin():
        row = session.get(ApplicationSession, UUID(body["id"]))
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    draft = client.post(
        f"/api/v1/application-sessions/{body['id']}/draft-answers",
        json={
            "questions": [
                {
                    "field_id": "q1",
                    "label": "Why us?",
                    "field_type": "TEXT",
                    "options": [],
                    "required": False,
                    "sensitive": False,
                }
            ],
            "expected_profile_revision": 1,
        },
    )
    assert draft.status_code == 409
    fresh = _session(client)
    assert fresh["id"] != body["id"]
    dash = client.get("/api/v1/dashboard").json()
    assert dash["prepared_sessions"] == 1  # expired session is not counted


def test_event_for_other_owner_session_not_found(client: TestClient) -> None:
    # RLS: a session owned by another account is invisible.
    response = client.post(
        "/api/v1/submission-events",
        json={
            "event_idempotency_key": str(uuid4()),
            "application_session_id": str(uuid4()),
            "evidence_type": "SUBMIT_CLICK",
            "evidence_source": "USER_GESTURE",
            "observed_at": datetime.now(UTC).isoformat(),
            "gesture_ref_hash": "e" * 64,
            "evidence": {},
        },
    )
    assert response.status_code == 404
