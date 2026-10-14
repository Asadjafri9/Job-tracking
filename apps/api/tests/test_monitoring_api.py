"""PostgreSQL-backed checks for monitored sources, runs, jobs, notifications (M5)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
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
    DiscoveredJob,
    MonitoredSource,
    MonitoringRun,
    Notification,
    Profile,
    ProfileFact,
    User,
)
from app.db.tenant import tenant_session
from app.main import app
from app.modules import monitoring as monitoring_module
from app.monitoring.fetch import FetchOutcome
from app.monitoring.scan import execute_monitoring_run

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "M5 API tests need migration and runtime database URLs", allow_module_level=True
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("M5 API tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)

LISTING_HTML = b"""
<html><body>
  <a href="/careers/swe-1">Software Engineer - job opening</a>
  <a href="/careers/ops-2">Operations Analyst - apply</a>
</body></html>"""


class _FakeFetcher:
    def __init__(self, outcomes: list[FetchOutcome]):
        self.outcomes = list(outcomes)
        self.calls: list[str] = []

    def fetch(self, url: str, etag: str | None = None) -> FetchOutcome:
        self.calls.append(url)
        return self.outcomes.pop(0)


@pytest.fixture
def owner_id() -> Iterator[UUID]:
    identity = uuid4()
    with Session(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://m5-api.local.test/issuer",
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
    auth = AuthContext(user_id=owner_id, token="m5-token", auth_time=datetime.now(UTC))
    app.dependency_overrides[require_auth] = lambda: auth
    monkeypatch.setattr(monitoring_module, "_runtime_engine", lambda: runtime_engine)
    monkeypatch.setattr(monitoring_module, "require_csrf", lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_source(client: TestClient, **overrides: object) -> dict:
    payload = {
        "public_url": "https://jobs.example.com/careers",
        "timezone": "America/New_York",
        "schedule": "DAILY",
        "scheduled_check_consent": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/monitored-sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_consented_source_is_active_with_next_run(client: TestClient) -> None:
    source = _create_source(client)
    assert source["state"] == "ACTIVE"
    assert source["next_run_at"] is not None
    assert source["setup_required"] is False
    assert source["scheduled_check_consented_at"] is not None


def test_create_without_consent_stays_setup_required(client: TestClient) -> None:
    source = _create_source(client, scheduled_check_consent=False)
    assert source["state"] == "PAUSED"
    assert source["next_run_at"] is None
    assert source["setup_required"] is True


def test_create_rejects_unsafe_urls(client: TestClient) -> None:
    for url in (
        "http://jobs.example.com/x",
        "https://127.0.0.1/x",
        "https://user:pw@jobs.example.com/x",
        "https://jobs.example.com:8443/x",
    ):
        response = client.post(
            "/api/v1/monitored-sources",
            json={
                "public_url": url,
                "timezone": "UTC",
                "scheduled_check_consent": True,
            },
        )
        assert response.status_code == 422, url


def test_create_rejects_bad_timezone(client: TestClient) -> None:
    response = client.post(
        "/api/v1/monitored-sources",
        json={
            "public_url": "https://jobs.example.com/x",
            "timezone": "Not/AZone",
            "scheduled_check_consent": True,
        },
    )
    assert response.status_code == 422


def test_saved_key_consent_requires_schedule_consent(client: TestClient) -> None:
    response = client.post(
        "/api/v1/monitored-sources",
        json={
            "public_url": "https://jobs.example.com/x",
            "timezone": "UTC",
            "saved_key_consent": True,
        },
    )
    assert response.status_code == 422


def test_manual_source_rejects_scheduled_consent(client: TestClient) -> None:
    """Scheduled consent on a MANUAL source would violate the DB constraint."""
    response = client.post(
        "/api/v1/monitored-sources",
        json={
            "public_url": "https://jobs.example.com/x",
            "timezone": "UTC",
            "schedule": "MANUAL",
            "scheduled_check_consent": True,
        },
    )
    assert response.status_code == 422


def test_switch_to_manual_clears_scheduled_consent(client: TestClient) -> None:
    source = _create_source(client)
    manual = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={"expected_revision": source["revision"], "schedule": "MANUAL"},
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["schedule"] == "MANUAL"
    assert manual.json()["scheduled_check_consented_at"] is None
    assert manual.json()["saved_key_consented_at"] is None
    assert manual.json()["next_run_at"] is None


def test_scheduled_consent_on_manual_source_rejected(client: TestClient) -> None:
    source = _create_source(
        client, schedule="MANUAL", scheduled_check_consent=False
    )
    response = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={
            "expected_revision": source["revision"],
            "scheduled_check_consent": True,
        },
    )
    assert response.status_code == 422


def test_source_limit_of_five(client: TestClient) -> None:
    for index in range(5):
        _create_source(client, public_url=f"https://jobs{index}.example.com/c")
    response = client.post(
        "/api/v1/monitored-sources",
        json={
            "public_url": "https://sixth.example.com/c",
            "timezone": "UTC",
            "scheduled_check_consent": True,
        },
    )
    assert response.status_code == 409


def test_patch_revision_conflict_and_pause_resume(client: TestClient) -> None:
    source = _create_source(client)
    conflict = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={"expected_revision": 99, "action": "pause"},
    )
    assert conflict.status_code == 409
    paused = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={"expected_revision": source["revision"], "action": "pause"},
    )
    assert paused.status_code == 200
    assert paused.json()["state"] == "PAUSED"
    assert paused.json()["next_run_at"] is None
    resumed = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={"expected_revision": source["revision"], "action": "resume"},
    )
    assert resumed.json()["state"] == "ACTIVE"
    assert resumed.json()["next_run_at"] is not None


def test_edit_stales_consent_until_reconfirmed(client: TestClient) -> None:
    source = _create_source(client)
    edited = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={
            "expected_revision": source["revision"],
            "region_selector": "job-list",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["revision"] == source["revision"] + 1
    assert edited.json()["setup_required"] is True
    assert edited.json()["next_run_at"] is None
    reconfirmed = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={
            "expected_revision": edited.json()["revision"],
            "scheduled_check_consent": True,
        },
    )
    assert reconfirmed.json()["setup_required"] is False
    assert reconfirmed.json()["state"] == "PAUSED"  # consent alone does not reactivate
    resumed = client.patch(
        f"/api/v1/monitored-sources/{source['id']}",
        json={
            "expected_revision": reconfirmed.json()["revision"],
            "action": "resume",
        },
    )
    assert resumed.json()["state"] == "ACTIVE"


def test_check_now_rate_limited(client: TestClient) -> None:
    source = _create_source(client)
    for _ in range(3):
        response = client.post(f"/api/v1/monitored-sources/{source['id']}/check-now")
        assert response.status_code == 201
        assert response.json()["run_kind"] == "MANUAL"
    blocked = client.post(f"/api/v1/monitored-sources/{source['id']}/check-now")
    assert blocked.status_code == 429


def test_delete_cancels_queued_runs(client: TestClient, owner_id: UUID) -> None:
    source = _create_source(client)
    client.post(f"/api/v1/monitored-sources/{source['id']}/check-now")
    response = client.delete(f"/api/v1/monitored-sources/{source['id']}")
    assert response.status_code == 204
    listed = client.get("/api/v1/monitored-sources")
    assert listed.json()["sources"] == []
    with tenant_session(runtime_engine, owner_id) as session:
        states = session.scalars(
            select(MonitoringRun.state).where(MonitoringRun.source_id == UUID(source["id"]))
        ).all()
    assert states == ["CANCELED"]


def test_notifications_roundtrip(client: TestClient, owner_id: UUID) -> None:
    _create_source(client)
    with tenant_session(runtime_engine, owner_id) as session:
        session.add(
            Notification(
                user_id=owner_id,
                event_key="k1",
                kind="JOB_MATCH",
                content="New match: Engineer",
            )
        )
    listed = client.get("/api/v1/notifications?unread=true")
    body = listed.json()
    assert body["unread_count"] == 1
    note = body["notifications"][0]
    read = client.post(f"/api/v1/notifications/{note['id']}/read")
    assert read.json()["read_at"] is not None
    assert client.get("/api/v1/notifications").json()["unread_count"] == 0


def _seeded_source(owner_id: UUID, url: str = "https://jobs.example.com/careers") -> UUID:
    with tenant_session(runtime_engine, owner_id) as session:
        source = MonitoredSource(
            user_id=owner_id,
            public_url=url,
            source_kind="HTML",
            state="ACTIVE",
            schedule="DAILY",
            timezone="UTC",
            scheduled_check_consented_at=datetime.now(UTC),
            consent_revision=1,
            next_run_at=datetime.now(UTC),
        )
        session.add(source)
        session.flush()
        return source.id


def _queued_run(owner_id: UUID, source_id: UUID) -> UUID:
    with tenant_session(runtime_engine, owner_id) as session:
        run = MonitoringRun(
            user_id=owner_id,
            source_id=source_id,
            schedule_revision=1,
            run_kind="MANUAL",
            request_id=uuid4(),
            state="QUEUED",
            completeness="UNKNOWN",
        )
        session.add(run)
        session.flush()
        return run.id


def _run_and_source(
    owner_id: UUID, run_id: UUID, source_id: UUID
) -> tuple[MonitoringRun, MonitoredSource]:
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        session.expunge_all()
        return run, source


def test_scan_discovers_jobs_and_notifies(owner_id: UUID) -> None:
    source_id = _seeded_source(owner_id)
    run_id = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        session.add(
            ProfileFact(
                user_id=owner_id,
                profile_id=session.scalar(select(Profile.id).where(Profile.user_id == owner_id)),
                fact_key="target_roles",
                value_type="JSON",
                value=["engineer"],
                allowed_purposes=["MONITORING"],
            )
        )
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher(
            [
                FetchOutcome(
                    status="OK",
                    url=source.public_url,
                    content=LISTING_HTML,
                    content_type="text/html",
                    etag='"e1"',
                )
            ]
        )
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    run, source = _run_and_source(owner_id, run_id, source_id)
    assert run.state == "SUCCEEDED"
    assert run.completeness == "COMPLETE"
    assert run.discovered_count == 2
    assert source.last_etag == '"e1"'
    with tenant_session(runtime_engine, owner_id) as session:
        jobs = session.scalars(
            select(DiscoveredJob.match_reason).where(
                DiscoveredJob.source_id == source_id
            )
        ).all()
        notes = session.scalars(
            select(Notification.kind).where(Notification.user_id == owner_id)
        ).all()
    assert len(jobs) == 2
    assert sum(1 for reason in jobs if reason) == 1  # only the engineer title matches
    assert len(notes) == 1
    assert all(kind == "JOB_MATCH" for kind in notes)


def test_scan_not_modified_marks_seen(owner_id: UUID) -> None:
    source_id = _seeded_source(owner_id)
    run_id = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher([FetchOutcome(status="NOT_MODIFIED", url=source.public_url)])
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    run, _ = _run_and_source(owner_id, run_id, source_id)
    assert run.state == "SUCCEEDED"
    assert run.completeness == "COMPLETE"


def test_scan_second_identical_run_no_duplicates(owner_id: UUID) -> None:
    source_id = _seeded_source(owner_id)
    for _ in range(2):
        run_id = _queued_run(owner_id, source_id)
        with tenant_session(runtime_engine, owner_id) as session:
            run = session.get(MonitoringRun, run_id)
            source = session.get(MonitoredSource, source_id)
            assert run is not None and source is not None
            fetcher = _FakeFetcher(
                [FetchOutcome(status="OK", url=source.public_url, content=LISTING_HTML)]
            )
            execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    with tenant_session(runtime_engine, owner_id) as session:
        count = session.scalars(
            select(DiscoveredJob.id).where(DiscoveredJob.source_id == source_id)
        ).all()
        notes = session.scalars(
            select(Notification.id).where(Notification.user_id == owner_id)
        ).all()
    assert len(count) == 2  # same postings deduped by canonical URL
    assert len(notes) == 2  # no duplicate notifications on unchanged content


def test_scan_meaningful_change_bumps_revision(owner_id: UUID) -> None:
    source_id = _seeded_source(owner_id)
    run_id = _queued_run(owner_id, source_id)
    changed_html = LISTING_HTML.replace(b"Software Engineer", b"Staff Software Engineer")
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher(
            [FetchOutcome(status="OK", url=source.public_url, content=LISTING_HTML)]
        )
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    run_id2 = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id2)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher(
            [FetchOutcome(status="OK", url=source.public_url, content=changed_html)]
        )
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    with tenant_session(runtime_engine, owner_id) as session:
        jobs = session.execute(
            select(DiscoveredJob.title, DiscoveredJob.meaningful_revision).where(
                DiscoveredJob.source_id == source_id
            )
        ).all()
        notes = session.scalars(
            select(Notification.event_key).where(Notification.user_id == owner_id)
        ).all()
    updated = [rev for title, rev in jobs if "Staff" in title]
    assert updated and updated[0] == 2
    assert any(":UPDATED:" in key for key in notes)


def test_scan_fetch_failure_records_honest_error(owner_id: UUID) -> None:
    from app.monitoring.fetch import FetchDenied

    class _Denying:
        def fetch(self, url: str, etag: str | None = None) -> FetchOutcome:
            raise FetchDenied("robots.txt disallows /careers")

    source_id = _seeded_source(owner_id)
    run_id = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        execute_monitoring_run(session, run, source, _Denying())  # type: ignore[arg-type]
    run, _ = _run_and_source(owner_id, run_id, source_id)
    assert run.state == "FAILED"
    assert "robots" in (run.redacted_error or "")
    with tenant_session(runtime_engine, owner_id) as session:
        notes = session.scalars(
            select(Notification).where(
                Notification.user_id == owner_id,
                Notification.kind == "SOURCE_STATUS",
            )
        ).all()
    assert len(notes) == 1


def test_each_failed_run_creates_a_notification(owner_id: UUID) -> None:
    """Failure notifications are keyed per run — a second failure alerts too."""
    from app.monitoring.fetch import FetchDenied

    class _Denying:
        def fetch(self, url: str, etag: str | None = None) -> FetchOutcome:
            raise FetchDenied("robots.txt disallows /careers")

    source_id = _seeded_source(owner_id)
    for _ in range(2):
        run_id = _queued_run(owner_id, source_id)
        with tenant_session(runtime_engine, owner_id) as session:
            run = session.get(MonitoringRun, run_id)
            source = session.get(MonitoredSource, source_id)
            assert run is not None and source is not None
            execute_monitoring_run(session, run, source, _Denying())  # type: ignore[arg-type]
    with tenant_session(runtime_engine, owner_id) as session:
        notes = session.scalars(
            select(Notification).where(
                Notification.user_id == owner_id,
                Notification.kind == "SOURCE_STATUS",
            )
        ).all()
    assert len(notes) == 2


OPS_ONLY_HTML = b"""
<html><body>
  <a href="/careers/ops-2">Operations Analyst - apply</a>
</body></html>"""

EMPTY_HTML = b"<html><body><p>No jobs right now</p></body></html>"


def _job_status(owner_id: UUID, source_id: UUID, url_part: str) -> str:
    with tenant_session(runtime_engine, owner_id) as session:
        status = session.scalar(
            select(DiscoveredJob.status).where(
                DiscoveredJob.source_id == source_id,
                DiscoveredJob.canonical_job_url.contains(url_part),
            )
        )
        assert status is not None
        return status


def _run_scan(owner_id: UUID, source_id: UUID, html: bytes) -> UUID:
    run_id = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher(
            [FetchOutcome(status="OK", url=source.public_url, content=html)]
        )
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    return run_id


def test_partial_scan_never_closes_absent_jobs(owner_id: UUID) -> None:
    """Closure needs absence in two consecutive COMPLETE scans; PARTIAL never closes."""
    source_id = _seeded_source(owner_id)
    _run_scan(owner_id, source_id, LISTING_HTML)  # complete: sees swe-1 + ops-2
    _run_scan(owner_id, source_id, OPS_ONLY_HTML)  # complete: swe-1 absent once
    assert _job_status(owner_id, source_id, "swe-1") == "NEW"

    partial_id = _run_scan(owner_id, source_id, EMPTY_HTML)  # PARTIAL, zero candidates
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, partial_id)
        assert run is not None and run.completeness == "PARTIAL"
    assert _job_status(owner_id, source_id, "swe-1") == "NEW"

    _run_scan(owner_id, source_id, OPS_ONLY_HTML)  # complete: swe-1 absent twice
    assert _job_status(owner_id, source_id, "swe-1") == "CLOSED"


def test_job_status_actions(client: TestClient, owner_id: UUID) -> None:
    source_id = _seeded_source(owner_id)
    with tenant_session(runtime_engine, owner_id) as session:
        job = DiscoveredJob(
            user_id=owner_id,
            source_id=source_id,
            canonical_job_url="https://jobs.example.com/j/1",
            title="Engineer",
            status="NEW",
        )
        session.add(job)
        session.flush()
        job_id = str(job.id)
    saved = client.patch(f"/api/v1/discovered-jobs/{job_id}", json={"action": "save"})
    assert saved.json()["status"] == "SAVED"
    dismissed = client.patch(f"/api/v1/discovered-jobs/{job_id}", json={"action": "dismiss"})
    assert dismissed.json()["status"] == "DISMISSED"
    listed = client.get("/api/v1/discovered-jobs?status=DISMISSED")
    assert len(listed.json()["jobs"]) == 1


def test_scan_duplicate_candidates_do_not_abort(owner_id: UUID) -> None:
    """The same posting twice on one page must not violate identity uniques."""
    duplicate_html = b"""
    <html><body>
      <a href="/careers/swe-1">Software Engineer - job</a>
      <a href="/careers/swe-1">Software Engineer - job</a>
    </body></html>"""
    source_id = _seeded_source(owner_id)
    run_id = _queued_run(owner_id, source_id)
    with tenant_session(runtime_engine, owner_id) as session:
        run = session.get(MonitoringRun, run_id)
        source = session.get(MonitoredSource, source_id)
        assert run is not None and source is not None
        fetcher = _FakeFetcher(
            [FetchOutcome(status="OK", url=source.public_url, content=duplicate_html)]
        )
        execute_monitoring_run(session, run, source, fetcher)  # type: ignore[arg-type]
    run, _ = _run_and_source(owner_id, run_id, source_id)
    assert run.state == "SUCCEEDED"
    with tenant_session(runtime_engine, owner_id) as session:
        count = session.scalars(
            select(DiscoveredJob.id).where(DiscoveredJob.source_id == source_id)
        ).all()
    assert len(count) == 1
