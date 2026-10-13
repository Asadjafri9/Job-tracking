"""Registered durable workload handlers.

Handlers run inside an owner-scoped runtime transaction derived from the
trusted job row; they never accept an owner from the job body. The daily
scan handler performs the claim-time revalidation required by the
monitoring contract and records an honest outcome until the fetch/match
pipeline lands in M5.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from app.ai.router import RoutingError, run_operation
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.jobs import enqueue_job
from app.db.models import (
    Document,
    DocumentExtraction,
    ExtensionGrant,
    IdempotencyRecord,
    MonitoredSource,
    MonitoringRun,
    QuotaReservation,
)
from app.db.models import Session as SessionRecord
from app.db.tenant import tenant_session
from app.modules.credentials import _key_encryption_provider
from app.storage.blob import DocumentStorage, StorageError, document_storage
from app.worker.parsing import (
    PARSE_VERSION,
    ParseResult,
    parse_document,
    split_sections,
)
from app.worker.registry import HANDLERS, JobContext, register
from app.worker.scheduler import SCAN_JOB_KIND, SCAN_JOB_REFERENCE_TYPE

logger = logging.getLogger("app.worker.handlers")

CLEANUP_JOB_KIND = "maintenance.owner_cleanup"
PARSE_JOB_KIND = "document.parse"
PARSE_JOB_REFERENCE_TYPE = "document"
EXTRACT_JOB_KIND = "document.extract_candidates"
EXTRACT_JOB_REFERENCE_TYPE = "document_extraction"
BLOB_CLEANUP_JOB_KIND = "document.blob_cleanup"
PIPELINE_PENDING_REASON = "daily_scan_pipeline_pending_m5"
SOURCE_STALE_REASON = "source_schedule_or_consent_changed"

OwnerWork = Callable[[OrmSession, JobContext], None]


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


def _document_storage() -> DocumentStorage:
    return document_storage()


def _daily_scan(session: OrmSession, context: JobContext) -> None:
    """Revalidate a dispatched daily run before any fetch/provider work."""
    now = datetime.now(UTC)
    if context.reference_type != SCAN_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("daily scan jobs must reference a monitoring run")
    run = session.scalar(
        select(MonitoringRun)
        .where(
            MonitoringRun.id == context.reference_id,
            MonitoringRun.user_id == context.owner_id,
        )
        .with_for_update()
    )
    if run is None or run.state != "QUEUED":
        return
    source = session.scalar(
        select(MonitoredSource).where(
            MonitoredSource.id == run.source_id,
            MonitoredSource.user_id == context.owner_id,
        )
    )
    still_scheduled = (
        source is not None
        and source.state == "ACTIVE"
        and source.schedule == "DAILY"
        and source.scheduled_check_consented_at is not None
        and source.consent_revision is not None
        and source.revision == run.schedule_revision
    )
    run.started_at = now
    run.ended_at = now
    if not still_scheduled:
        run.state = "CANCELED"
        run.redacted_error = SOURCE_STALE_REASON
        logger.info(
            "daily scan canceled before dispatch: run=%s source stale or unconsented", run.id
        )
        return
    run.state = "FAILED"
    run.completeness = "UNKNOWN"
    run.redacted_error = PIPELINE_PENDING_REASON
    logger.info("daily scan run %s recorded pending pipeline implementation", run.id)


def _owner_cleanup(session: OrmSession, context: JobContext) -> None:
    """Purge expired ephemeral records owned by the job's verified owner."""
    now = datetime.now(UTC)
    session.execute(
        delete(ExtensionGrant).where(
            ExtensionGrant.user_id == context.owner_id,
            or_(
                ExtensionGrant.consumed_at.is_not(None),
                ExtensionGrant.revoked_at.is_not(None),
                ExtensionGrant.expires_at <= now,
            ),
        )
    )
    session.execute(
        delete(SessionRecord).where(
            SessionRecord.user_id == context.owner_id,
            or_(SessionRecord.revoked_at.is_not(None), SessionRecord.expires_at <= now),
        )
    )
    session.execute(
        delete(IdempotencyRecord).where(
            IdempotencyRecord.user_id == context.owner_id,
            IdempotencyRecord.expires_at <= now,
        )
    )
    session.execute(
        delete(QuotaReservation).where(
            QuotaReservation.user_id == context.owner_id,
            QuotaReservation.expires_at <= now,
        )
    )


def _parse_document(session: OrmSession, context: JobContext, result: ParseResult) -> None:
    """Store a bounded parse outcome for the job's document, restart-safely."""
    if context.reference_type != PARSE_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("document parse jobs must reference a document")
    document = session.scalar(
        select(Document)
        .where(
            Document.id == context.reference_id,
            Document.user_id == context.owner_id,
        )
        .with_for_update()
    )
    if document is None or document.original_state == "DELETED":
        return
    existing = session.scalar(
        select(DocumentExtraction).where(
            DocumentExtraction.user_id == context.owner_id,
            DocumentExtraction.document_id == document.id,
            DocumentExtraction.document_revision == document.revision,
            DocumentExtraction.parse_version == PARSE_VERSION,
        )
    )
    if existing is not None:
        return
    if result.status == "OK":
        document.parse_state = "PARSED"
        extraction = DocumentExtraction(
            user_id=context.owner_id,
            document_id=document.id,
            document_revision=document.revision,
            parse_version=PARSE_VERSION,
            extracted_text=result.text,
            source_anchors=result.anchors,
            candidates=[],
            candidate_count=0,
            review_state="REVIEW_REQUIRED",
        )
        session.add(extraction)
        session.flush()
        # Candidate generation is a separate durable job so provider work
        # never extends the parse transaction or retries parsing.
        enqueue_job(
            session,
            owner_id=context.owner_id,
            kind=EXTRACT_JOB_KIND,
            reference_type=EXTRACT_JOB_REFERENCE_TYPE,
            reference_id=extraction.id,
        )
    else:
        document.parse_state = "FAILED"
        session.add(
            DocumentExtraction(
                user_id=context.owner_id,
                document_id=document.id,
                document_revision=document.revision,
                parse_version=PARSE_VERSION,
                extracted_text=None,
                source_anchors=[],
                candidates=[],
                candidate_count=0,
                review_state="FAILED",
                redacted_error=result.error or "parser failed",
            )
        )


async def _run_owner_scoped(context: JobContext, work: OwnerWork) -> None:
    def execute() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            work(session, context)

    await asyncio.to_thread(execute)


async def handle_daily_scan(context: JobContext, _stopped: asyncio.Event) -> None:
    await _run_owner_scoped(context, _daily_scan)


async def handle_owner_cleanup(context: JobContext, _stopped: asyncio.Event) -> None:
    await _run_owner_scoped(context, _owner_cleanup)


async def handle_document_parse(context: JobContext, _stopped: asyncio.Event) -> None:
    """Fetch the owner blob, parse it in a bounded child, persist the result."""
    if context.reference_type != PARSE_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("document parse jobs must reference a document")

    def execute() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            document = session.scalar(
                select(Document).where(
                    Document.id == context.reference_id,
                    Document.user_id == context.owner_id,
                    Document.original_state == "READY",
                )
            )
            if document is None or document.parse_state != "QUEUED":
                return
            document.parse_state = "RUNNING"
            storage_key = document.storage_key
            media_type = document.media_type
            session.flush()
        try:
            blob = _document_storage().get(storage_key)
        except StorageError:
            result = ParseResult(status="FAILED", error="document blob is unavailable")
        else:
            import tempfile

            suffix = ".pdf" if media_type == "application/pdf" else ".docx"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
                handle.write(blob)
                handle.flush()
                result = parse_document(handle.name, media_type)
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            _parse_document(session, context, result)

    await asyncio.to_thread(execute)


async def handle_extract_candidates(context: JobContext, _stopped: asyncio.Event) -> None:
    """Generate anchored profile candidates through consented providers.

    Runs unattended as BACKGROUND purpose: without the required provider
    consent the extraction simply keeps its empty candidate list and manual
    review remains available. No candidate is ever auto-confirmed.
    """
    if (
        context.reference_type != EXTRACT_JOB_REFERENCE_TYPE
        or context.reference_id is None
    ):
        raise ValueError("extraction jobs must reference a document_extraction")

    def execute() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            extraction = session.scalar(
                select(DocumentExtraction)
                .where(
                    DocumentExtraction.id == context.reference_id,
                    DocumentExtraction.user_id == context.owner_id,
                )
                .with_for_update()
            )
            if extraction is None or not extraction.extracted_text:
                return
            document = session.scalar(
                select(Document).where(
                    Document.id == extraction.document_id,
                    Document.user_id == context.owner_id,
                )
            )
            if (
                document is None
                or document.original_state == "DELETED"
                or document.revision != extraction.document_revision
                or extraction.candidates
            ):
                return
            sections = split_sections(
                ParseResult(
                    status="OK",
                    text=extraction.extracted_text,
                    anchors=list(extraction.source_anchors or []),
                )
            )
            if not sections:
                return
            try:
                result = run_operation(
                    session,
                    owner_id=context.owner_id,
                    kind="EXTRACTION",
                    request_payload={
                        "document_type": document.document_type,
                        "sections": sections,
                    },
                    purpose="BACKGROUND",
                    idempotency_key=uuid5(
                        NAMESPACE_URL, f"extract:{extraction.id}"
                    ),
                    key_encryption=_key_encryption_provider(),
                )
            except RoutingError as error:
                if error.code != "consent_required":
                    extraction.review_state = "FAILED"
                    extraction.redacted_error = error.code
                session.flush()
                return
            if result.state != "SUCCEEDED" or result.content is None:
                extraction.review_state = "FAILED"
                extraction.redacted_error = result.state.lower()
                session.flush()
                return
            candidates = []
            for candidate in result.content.get("candidates", []):
                entry = dict(candidate)
                entry["decision"] = None
                candidates.append(entry)
            extraction.candidates = candidates
            extraction.candidate_count = len(candidates)
            extraction.redacted_error = None
            session.flush()

    await asyncio.to_thread(execute)


async def handle_blob_cleanup(context: JobContext, _stopped: asyncio.Event) -> None:
    """Delete a deleted document's private blob; job retries cover failures."""
    if context.reference_type != PARSE_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("blob cleanup jobs must reference a document")

    def execute() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            storage_key = session.scalar(
                select(Document.storage_key).where(
                    Document.id == context.reference_id,
                    Document.user_id == context.owner_id,
                    Document.original_state == "DELETED",
                )
            )
        if storage_key is None:
            return
        _document_storage().delete(storage_key)

    await asyncio.to_thread(execute)


def register_builtin_handlers() -> None:
    """Register durable workload handlers once per worker process."""
    if SCAN_JOB_KIND not in HANDLERS:
        register(SCAN_JOB_KIND, handle_daily_scan)
    if CLEANUP_JOB_KIND not in HANDLERS:
        register(CLEANUP_JOB_KIND, handle_owner_cleanup)
    if PARSE_JOB_KIND not in HANDLERS:
        register(PARSE_JOB_KIND, handle_document_parse)
    if EXTRACT_JOB_KIND not in HANDLERS:
        register(EXTRACT_JOB_KIND, handle_extract_candidates)
    if BLOB_CLEANUP_JOB_KIND not in HANDLERS:
        register(BLOB_CLEANUP_JOB_KIND, handle_blob_cleanup)
