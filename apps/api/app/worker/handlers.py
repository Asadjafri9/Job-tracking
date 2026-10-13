"""Registered durable workload handlers.

Handlers run inside an owner-scoped runtime transaction derived from the
trusted job row; they never accept an owner from the job body. The scan
handler revalidates the run's schedule/consent at claim time, performs the
bounded public fetch outside the transaction, then applies the extracted
diff in a second owner transaction.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy import create_engine, delete, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from app.ai.router import RoutingError, run_operation
from app.config import get_settings
from app.db.connection import sqlalchemy_url
from app.db.jobs import enqueue_job
from app.db.models import (
    ApplicationSession,
    DeletionJournal,
    Document,
    DocumentExtraction,
    EmailDraft,
    ExportArtifact,
    ExtensionGrant,
    IdempotencyRecord,
    Job,
    MonitoredSource,
    MonitoringRun,
    QuotaReservation,
)
from app.db.models import Session as SessionRecord
from app.db.tenant import tenant_session
from app.modules.credentials import _key_encryption_provider
from app.monitoring.fetch import (
    FetchDenied,
    Fetcher,
    FetchFailed,
    FetchOutcome,
    FetchUnsupported,
)
from app.monitoring.scan import apply_scan_outcome, begin_run, record_fetch_failure
from app.privacy.exporting import build_export_zip
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
EXPORT_JOB_KIND = "privacy.export"
EXPORT_JOB_REFERENCE_TYPE = "export_artifact"
DELETE_JOB_KIND = "privacy.account_delete"
EXPORT_DOWNLOAD_TTL = timedelta(hours=24)
BUILD_TIMEOUT = timedelta(hours=1)
DRAFT_RETENTION = timedelta(days=30)
SOURCE_STALE_REASON = "source_schedule_or_consent_changed"

OwnerWork = Callable[[OrmSession, JobContext], None]


@lru_cache(maxsize=1)
def _runtime_engine() -> Engine:
    return create_engine(sqlalchemy_url(get_settings().database_url), pool_pre_ping=True)


def _document_storage() -> DocumentStorage:
    return document_storage()


def _owner_state(session: OrmSession) -> str | None:
    """The job owner's current account state through the self-scoped view."""
    state = session.scalar(
        sa.text("SELECT state FROM copilot_current_user LIMIT 1")
    )
    return state if isinstance(state, str) else None


def _claim_scan(session: OrmSession, context: JobContext) -> MonitoringRun | None:
    """Revalidate a dispatched run before any fetch/provider work."""
    if context.reference_type != SCAN_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("scan jobs must reference a monitoring run")
    if _owner_state(session) != "ACTIVE":
        run = session.scalar(
            select(MonitoringRun).where(
                MonitoringRun.id == context.reference_id,
                MonitoringRun.user_id == context.owner_id,
            )
        )
        if run is not None and run.state == "QUEUED":
            run.state = "CANCELED"
            run.started_at = run.ended_at = datetime.now(UTC)
            run.redacted_error = "account_not_active"
        return None
    run = session.scalar(
        select(MonitoringRun)
        .where(
            MonitoringRun.id == context.reference_id,
            MonitoringRun.user_id == context.owner_id,
        )
        .with_for_update()
    )
    if run is None or run.state != "QUEUED":
        return None
    source = session.scalar(
        select(MonitoredSource).where(
            MonitoredSource.id == run.source_id,
            MonitoredSource.user_id == context.owner_id,
        )
    )
    if run.run_kind == "MANUAL":
        still_valid = (
            source is not None
            and source.state in {"ACTIVE", "PAUSED"}
            and source.revision == run.schedule_revision
        )
    else:
        still_valid = (
            source is not None
            and source.state == "ACTIVE"
            and source.schedule == "DAILY"
            and source.scheduled_check_consented_at is not None
            and source.consent_revision is not None
            and source.revision == run.schedule_revision
        )
    if not still_valid:
        run.state = "CANCELED"
        run.started_at = run.ended_at = datetime.now(UTC)
        run.redacted_error = SOURCE_STALE_REASON
        logger.info(
            "scan canceled before dispatch: run=%s source stale or unconsented", run.id
        )
        return None
    begin_run(run)
    return run


async def handle_daily_scan(context: JobContext, _stopped: asyncio.Event) -> None:
    """Claim the run, fetch outside the transaction, then apply the diff."""

    def execute() -> None:
        fetcher = Fetcher()
        outcome: FetchOutcome | None = None
        failure: Exception | None = None
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            run = _claim_scan(session, context)
            if run is None:
                return
            source = session.get(MonitoredSource, run.source_id)
            if source is None:
                return
            public_url, etag = source.public_url, source.last_etag
            run_id = run.id
        try:
            outcome = fetcher.fetch(public_url, etag=etag)
        except (FetchDenied, FetchFailed, FetchUnsupported) as exc:
            failure = exc
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            run = session.scalar(
                select(MonitoringRun)
                .where(
                    MonitoringRun.id == run_id,
                    MonitoringRun.user_id == context.owner_id,
                )
                .with_for_update()
            )
            if run is None:
                return
            source = session.scalar(
                select(MonitoredSource).where(
                    MonitoredSource.id == run.source_id,
                    MonitoredSource.user_id == context.owner_id,
                )
            )
            if run.state != "RUNNING" or source is None:
                return
            if _owner_state(session) != "ACTIVE":
                run.state = "CANCELED"
                run.ended_at = datetime.now(UTC)
                run.redacted_error = "account_not_active"
                return
            if source.state == "DELETED" or source.revision != run.schedule_revision:
                run.state = "CANCELED"
                run.ended_at = datetime.now(UTC)
                run.redacted_error = SOURCE_STALE_REASON
                return
            if failure is not None:
                record_fetch_failure(session, run, failure)
            elif outcome is not None:
                apply_scan_outcome(session, run, source, outcome)

    await asyncio.to_thread(execute)


def _owner_cleanup(session: OrmSession, context: JobContext) -> list[str]:
    """Purge expired ephemeral records owned by the job's verified owner.

    Returns artifact storage keys whose blobs must be deleted after commit;
    the job is restart-safe because unprocessed work simply remains for the
    next tick.
    """
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
    session.execute(
        update(ApplicationSession)
        .where(
            ApplicationSession.user_id == context.owner_id,
            ApplicationSession.expires_at.is_not(None),
            ApplicationSession.expires_at <= now,
            ApplicationSession.state.in_(
                ["PREPARED", "ANALYZING", "READY_TO_REVIEW"]
            ),
        )
        .values(state="ABANDONED")
    )
    session.execute(
        update(EmailDraft)
        .where(
            EmailDraft.user_id == context.owner_id,
            EmailDraft.state.in_(["DRAFT", "READY_FOR_REVIEW", "COMPOSE_OPENED"]),
            EmailDraft.updated_at <= now - DRAFT_RETENTION,
        )
        .values(state="CANCELED")
    )
    session.execute(
        update(Job)
        .where(
            Job.user_id == context.owner_id,
            Job.state == "QUEUED",
            Job.expires_at.is_not(None),
            Job.expires_at <= now,
        )
        .values(state="CANCELED", stage="expired")
    )
    stale_builds = session.scalars(
        select(ExportArtifact).where(
            ExportArtifact.user_id == context.owner_id,
            ExportArtifact.state == "BUILDING",
            ExportArtifact.created_at <= now - BUILD_TIMEOUT,
        )
    ).all()
    for artifact in stale_builds:
        artifact.state = "EXPIRED"
        artifact.redacted_error = "build_timeout"
    expired = session.scalars(
        select(ExportArtifact).where(
            ExportArtifact.user_id == context.owner_id,
            ExportArtifact.state == "READY",
            ExportArtifact.expires_at <= now,
        )
    ).all()
    keys: list[str] = []
    for artifact in expired:
        artifact.state = "EXPIRED"
        if artifact.storage_key:
            keys.append(artifact.storage_key)
    return keys


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


async def handle_owner_cleanup(context: JobContext, _stopped: asyncio.Event) -> None:
    keys: list[str] = []

    def execute() -> None:
        nonlocal keys
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            keys = _owner_cleanup(session, context)

    await asyncio.to_thread(execute)
    storage = _document_storage()
    for key in keys:
        try:
            storage.delete(key)
        except StorageError:
            logger.warning("expired export blob cleanup failed: %s", key)


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


async def handle_export(context: JobContext, _stopped: asyncio.Event) -> None:
    """Build the owner-scoped export ZIP and publish a private artifact.

    The snapshot is assembled inside one owner transaction so all exported
    rows are consistent; the artifact only becomes READY after the blob is
    written and the owner is still ACTIVE at publish time.
    """
    if context.reference_type != EXPORT_JOB_REFERENCE_TYPE or context.reference_id is None:
        raise ValueError("export jobs must reference an export artifact")

    def execute() -> None:
        storage = _document_storage()
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            artifact = session.scalar(
                select(ExportArtifact)
                .where(
                    ExportArtifact.id == context.reference_id,
                    ExportArtifact.user_id == context.owner_id,
                )
                .with_for_update()
            )
            if artifact is None or artifact.state != "BUILDING":
                return
            if _owner_state(session) != "ACTIVE":
                artifact.state = "DELETED"
                artifact.redacted_error = "account_not_active"
                return
            zip_bytes, _checksums = build_export_zip(
                session, context.owner_id, blob_getter=storage.get
            )
            storage_key = f"exports/{context.owner_id}/{artifact.id}.zip"
            try:
                storage.put(storage_key, zip_bytes, "application/zip")
            except StorageError:
                # A crashed attempt can leave an orphaned blob at this key;
                # ZIP bytes differ per build, so remove it and rewrite.
                storage.delete(storage_key)
                storage.put(storage_key, zip_bytes, "application/zip")
            # Recheck before publication: a deletion or suspension that
            # began while the ZIP was being assembled must not publish.
            if _owner_state(session) != "ACTIVE":
                artifact.state = "DELETED"
                artifact.redacted_error = "account_not_active"
                return
            artifact.storage_key = storage_key
            artifact.size_bytes = len(zip_bytes)
            artifact.sha256 = hashlib.sha256(zip_bytes).hexdigest()
            artifact.expires_at = datetime.now(UTC) + EXPORT_DOWNLOAD_TTL
            artifact.state = "READY"

    await asyncio.to_thread(execute)


_DELETE_TABLES = (
    "notifications",
    "discovered_jobs",
    "monitoring_runs",
    "monitored_sources",
    "application_answers",
    "application_status_events",
    "submission_events",
    "applications",
    "application_sessions",
    "email_draft_events",
    "email_draft_documents",
    "email_drafts",
    "ai_attempts",
    "ai_operations",
    "provider_routes",
    "provider_credentials",
    "provider_settings",
    "document_extractions",
    "documents",
    "profile_fact_versions",
    "profile_facts",
    "profiles",
    "export_artifacts",
    "extension_grants",
    "sessions",
    "idempotency_records",
    "quota_reservations",
    "audit_events",
    "jobs",
)


async def handle_account_delete(context: JobContext, _stopped: asyncio.Event) -> None:
    """Stage 2: erase owned data and tombstone identity after the journal.

    The independent journal row written by the API endpoint is the receipt;
    it must exist before any deletion runs. Document and export blobs are
    collected first and deleted outside the transaction, then all owned
    rows are removed in FK-safe order and the user row is tombstoned. Late
    results cannot repopulate data because handlers re-check owner state.
    """
    owner_hash = hashlib.sha256(str(context.owner_id).encode()).hexdigest()

    def collect_keys() -> list[str]:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            journal = session.scalar(
                select(DeletionJournal).where(
                    DeletionJournal.user_id_hash == owner_hash
                )
            )
            if journal is None:
                raise ValueError("deletion journal missing; refusing deletion")
            keys = session.scalars(
                select(Document.storage_key).where(
                    Document.user_id == context.owner_id
                )
            ).all()
            keys = list(keys)
            keys += [
                key
                for key in session.scalars(
                    select(ExportArtifact.storage_key).where(
                        ExportArtifact.user_id == context.owner_id,
                        ExportArtifact.storage_key.is_not(None),
                    )
                ).all()
                if key is not None
            ]
            return keys

    keys = await asyncio.to_thread(collect_keys)
    storage = _document_storage()
    for key in keys:
        try:
            storage.delete(key)
        except StorageError:
            logger.warning("account deletion blob cleanup failed: %s", key)

    def delete_data() -> None:
        with tenant_session(_runtime_engine(), context.owner_id) as session:
            state = _owner_state(session)
            if state == "DELETED":
                return
            if state != "DELETING":
                logger.warning(
                    "account deletion skipped: owner %s state %s", context.owner_id, state
                )
                return
            for table in _DELETE_TABLES:
                session.execute(
                    sa.text(f'DELETE FROM "{table}" WHERE user_id = :owner'),
                    {"owner": context.owner_id},
                )
            session.execute(sa.text("SELECT copilot_tombstone_user()"))
            session.flush()

    await asyncio.to_thread(delete_data)


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
    if EXPORT_JOB_KIND not in HANDLERS:
        register(EXPORT_JOB_KIND, handle_export)
    if DELETE_JOB_KIND not in HANDLERS:
        register(DELETE_JOB_KIND, handle_account_delete)
