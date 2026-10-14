"""PostgreSQL checks for the consented extraction-candidates job (DOC-003)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from app.ai.router import OperationResult, RoutingError
from app.db.connection import sqlalchemy_url
from app.db.models import Document, DocumentExtraction, Profile, User
from app.db.tenant import tenant_session
from app.worker import handlers
from app.worker.registry import JobContext

MIGRATION_URL = os.getenv("DB001_DATABASE_URL")
RUNTIME_URL = os.getenv("DB002_RUNTIME_DATABASE_URL")
if MIGRATION_URL is None or RUNTIME_URL is None:
    pytest.skip(
        "extraction handler tests need migration and runtime database URLs",
        allow_module_level=True,
    )
if any(
    urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
    for url in (MIGRATION_URL, RUNTIME_URL)
):
    pytest.skip("extraction handler tests are restricted to loopback", allow_module_level=True)

migration_engine: Engine = create_engine(sqlalchemy_url(MIGRATION_URL), pool_pre_ping=True)
runtime_engine: Engine = create_engine(sqlalchemy_url(RUNTIME_URL), pool_pre_ping=True)


@pytest.fixture
def patched_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setattr(handlers, "_runtime_engine", lambda: runtime_engine)
    yield runtime_engine


@pytest.fixture
def seeded(patched_runtime: Engine) -> Iterator[tuple[UUID, UUID, UUID]]:
    identity = uuid4()
    with OrmSession(migration_engine) as session, session.begin():
        session.add(
            User(
                id=identity,
                issuer="https://extract.local.test/issuer",
                subject=str(uuid4()),
                directory_object_id=uuid4(),
                login_email=f"{identity}@example.test",
                login_email_verified=True,
            )
        )
        session.flush()
        session.add(Profile(user_id=identity))
    with tenant_session(patched_runtime, identity) as session:
        document = Document(
            user_id=identity,
            document_type="RESUME",
            storage_key="extract-seed",
            file_name="resume.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="b" * 64,
            original_state="READY",
            parse_state="PARSED",
        )
        session.add(document)
        session.flush()
        extraction = DocumentExtraction(
            user_id=identity,
            document_id=document.id,
            document_revision=document.revision,
            parse_version="parser-v1",
            extracted_text="Experience\n\nSenior Engineer at Example Corp",
            source_anchors=[{"page": 1, "block": 0, "excerpt": "Example Corp"}],
            candidates=[],
            candidate_count=0,
            review_state="REVIEW_REQUIRED",
        )
        session.add(extraction)
        session.flush()
        document_id, extraction_id = document.id, extraction.id
    try:
        yield identity, document_id, extraction_id
    finally:
        with migration_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == identity))


def _context(owner: UUID, extraction: UUID) -> JobContext:
    return JobContext(
        id=uuid4(),
        owner_id=owner,
        kind=handlers.EXTRACT_JOB_KIND,
        reference_type=handlers.EXTRACT_JOB_REFERENCE_TYPE,
        reference_id=extraction,
        attempt=1,
    )


def _extraction(owner: UUID, extraction_id: UUID) -> DocumentExtraction:
    with OrmSession(migration_engine) as session:
        row = session.scalar(
            select(DocumentExtraction).where(
                DocumentExtraction.user_id == owner,
                DocumentExtraction.id == extraction_id,
            )
        )
        assert row is not None
        session.expunge(row)
        return row


def _result(state: str, content: dict[str, object] | None = None) -> OperationResult:
    return OperationResult(
        operation_id=uuid4(),
        state=state,
        outcome="dispatched",
        content=content,
        provider="XAI" if state == "SUCCEEDED" else None,
        model="grok-4.7" if state == "SUCCEEDED" else None,
        replayed=False,
    )


def test_success_writes_candidates_with_pending_decisions(
    seeded: tuple[UUID, UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _, extraction_id = seeded
    seen: dict[str, object] = {}

    def stub_run(session: OrmSession, **kwargs: object) -> OperationResult:
        seen.update(kwargs)
        return _result(
            "SUCCEEDED",
            {
                "candidates": [
                    {
                        "fact_key": "employers.recent",
                        "value_type": "TEXT",
                        "value": "Example Corp",
                        "section_id": 0,
                        "anchor": {"page": 1, "block": 0},
                    }
                ]
            },
        )

    monkeypatch.setattr(handlers, "run_operation", stub_run)
    asyncio.run(handlers.handle_extract_candidates(_context(owner, extraction_id), asyncio.Event()))

    assert seen["purpose"] == "BACKGROUND"
    assert seen["kind"] == "EXTRACTION"
    payload_sections = seen["request_payload"]["sections"]  # type: ignore[index]
    assert payload_sections and "Example Corp" in payload_sections[0]["text"]

    extraction = _extraction(owner, extraction_id)
    assert extraction.candidate_count == 1
    assert extraction.candidates[0]["decision"] is None
    assert extraction.candidates[0]["value"] == "Example Corp"
    assert extraction.review_state == "REVIEW_REQUIRED"


def test_missing_background_consent_leaves_manual_review(
    seeded: tuple[UUID, UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _, extraction_id = seeded

    def stub_run(session: OrmSession, **kwargs: object) -> OperationResult:
        raise RoutingError("consent_required", "background provider consent is required")

    monkeypatch.setattr(handlers, "run_operation", stub_run)
    asyncio.run(handlers.handle_extract_candidates(_context(owner, extraction_id), asyncio.Event()))

    extraction = _extraction(owner, extraction_id)
    assert extraction.candidates == []
    assert extraction.review_state == "REVIEW_REQUIRED"
    assert extraction.redacted_error is None


def test_provider_failure_marks_review_failed(
    seeded: tuple[UUID, UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _, extraction_id = seeded

    def stub_run(session: OrmSession, **kwargs: object) -> OperationResult:
        raise RoutingError("providers_unavailable", "all eligible routes failed")

    monkeypatch.setattr(handlers, "run_operation", stub_run)
    asyncio.run(handlers.handle_extract_candidates(_context(owner, extraction_id), asyncio.Event()))

    extraction = _extraction(owner, extraction_id)
    assert extraction.review_state == "FAILED"
    assert extraction.redacted_error == "providers_unavailable"


def test_deleted_source_skips_dispatch(
    seeded: tuple[UUID, UUID, UUID],
    patched_runtime: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, document_id, extraction_id = seeded
    called = False

    def stub_run(session: OrmSession, **kwargs: object) -> OperationResult:
        nonlocal called
        called = True
        return _result("SUCCEEDED", {"candidates": []})

    with tenant_session(patched_runtime, owner) as session:
        document = session.get(Document, document_id)
        assert document is not None
        document.original_state = "DELETED"

    monkeypatch.setattr(handlers, "run_operation", stub_run)
    asyncio.run(handlers.handle_extract_candidates(_context(owner, extraction_id), asyncio.Event()))
    assert called is False
