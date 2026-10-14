"""Monitoring run pipeline (MON-003): fetch, extract, dedupe, match, notify.

Runs inside the job's owner-scoped runtime transaction. Job identity uses a
native stable ID or the canonical public URL; title/employer are review hints
only. Jobs are never closed after one scan — closure requires absence from
two consecutive COMPLETE successful scans. Notifications use exact dedupe
keys ``{job}:{event}:{meaningful_revision}`` via the unique event_key.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import (
    DiscoveredJob,
    MonitoredSource,
    MonitoringRun,
    Notification,
    ProfileFact,
)
from app.monitoring.extract import JobCandidate, extract_candidates
from app.monitoring.fetch import (
    FetchDenied,
    Fetcher,
    FetchFailed,
    FetchOutcome,
    FetchUnsupported,
)

logger = logging.getLogger("app.monitoring.scan")

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ref",
    "source",
}
def canonical_job_url(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname:
        return None
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in TRACKING_PARAMS
        ]
    )
    clean = (parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") or "/", query, "")
    return urlunsplit(clean)[:2048]


def _monitoring_preferences(session: Session, user_id: UUID) -> dict[str, list[str]]:
    facts = [
        fact
        for fact in session.scalars(
            select(ProfileFact).where(
                ProfileFact.user_id == user_id,
                ProfileFact.is_active.is_(True),
            )
        )
        if "MONITORING" in (fact.allowed_purposes or [])
    ]
    prefs: dict[str, list[str]] = {"roles": [], "locations": []}
    remote: list[str] = []
    for fact in facts:
        key = fact.fact_key.lower()
        values = fact.value if isinstance(fact.value, list) else [fact.value]
        tokens = [str(v).lower().strip() for v in values if v]
        if any(term in key for term in ("role", "title", "keyword")):
            prefs["roles"].extend(tokens)
        elif any(term in key for term in ("location", "city", "region", "country")):
            prefs["locations"].extend(tokens)
        elif "remote" in key:
            remote.extend(tokens)
    prefs["remote"] = remote
    return prefs


def _match_reason(candidate: JobCandidate, prefs: dict[str, list[str]]) -> str | None:
    text = f"{candidate.title} {candidate.location or ''}".lower()
    hits: list[str] = []
    for role in prefs["roles"]:
        if role and role in text:
            hits.append(f"role:{role}")
    for location in prefs["locations"]:
        if location and location in text:
            hits.append(f"location:{location}")
    if prefs["remote"] and candidate.is_remote is not None:
        wants_remote = any(v in {"true", "yes", "remote", "1"} for v in prefs["remote"])
        if candidate.is_remote == wants_remote:
            hits.append("remote:match")
    if not any(prefs.values()):
        return "no monitoring preferences configured; all discoveries reported"
    return "deterministic: " + ", ".join(hits[:5]) if hits else None


def _notify_new(
    session: Session,
    user_id: UUID,
    job_id: UUID | None,
    run_id: UUID,
    kind: str,
    event: str,
    revision: int,
    content: str,
) -> None:
    key = f"{job_id}:{event}:r{revision}"
    session.execute(
        pg_insert(Notification)
        .values(
            user_id=user_id,
            discovered_job_id=job_id,
            monitoring_run_id=run_id,
            event_key=key,
            kind=kind,
            content=content[:2048],
        )
        .on_conflict_do_nothing(index_elements=["user_id", "event_key"])
    )


def _previous_complete_run(
    session: Session, source_id: UUID, exclude_id: UUID
) -> datetime | None:
    return session.scalar(
        select(MonitoringRun.started_at)
        .where(
            MonitoringRun.source_id == source_id,
            MonitoringRun.id != exclude_id,
            MonitoringRun.state == "SUCCEEDED",
            MonitoringRun.completeness == "COMPLETE",
        )
        .order_by(MonitoringRun.started_at.desc())
        .limit(1)
    )


def _upsert_candidates(
    session: Session, run: MonitoringRun, candidates: list[JobCandidate]
) -> int:
    """Diff candidates against stored jobs; return count of new/updated rows."""
    prefs = _monitoring_preferences(session, run.user_id)
    rows = list(
        session.scalars(
            select(DiscoveredJob).where(
                DiscoveredJob.user_id == run.user_id,
                DiscoveredJob.source_id == run.source_id,
            )
        ).all()
    )
    changed = 0
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for cand in candidates:
        url = canonical_job_url(cand.url)
        if cand.external_id is None and url is None:
            continue
        if (cand.external_id and cand.external_id in seen_ids) or (
            url and url in seen_urls
        ):
            continue  # duplicate posting identity on the same page
        if cand.external_id:
            seen_ids.add(cand.external_id)
        if url:
            seen_urls.add(url)
        match_reason = _match_reason(cand, prefs)
        job = next(
            (
                row
                for row in rows
                if (cand.external_id and row.native_id == cand.external_id)
                or (url and row.canonical_job_url == url)
            ),
            None,
        )
        now = datetime.now(UTC)
        if job is None:
            job = DiscoveredJob(
                user_id=run.user_id,
                source_id=run.source_id,
                native_id_namespace="source-external-id" if cand.external_id else None,
                native_id=cand.external_id,
                canonical_job_url=url,
                # Client clock like run.started_at — keeps closure comparisons
                # in one clock domain (server now() can skew ahead of us).
                last_seen_at=now,
                title=cand.title,
                employer=cand.employer,
                location=cand.location,
                is_remote=cand.is_remote,
                evidence_anchors=cand.anchors,
                match_reason=match_reason,
                status="NEW",
            )
            session.add(job)
            session.flush()
            rows.append(job)
            changed += 1
            if match_reason:
                _notify_new(
                    session,
                    run.user_id,
                    job.id,
                    run.id,
                    "JOB_MATCH",
                    "NEW",
                    job.meaningful_revision,
                    f"New match on monitored source: {job.title}"
                    + (f" at {job.employer}" if job.employer else ""),
                )
            continue
        job.last_seen_at = now
        url_conflict = url is not None and any(
            row is not job and row.canonical_job_url == url for row in rows
        )
        dirty = (
            job.title != cand.title
            or job.employer != cand.employer
            or job.location != cand.location
            or job.is_remote != cand.is_remote
            or (url is not None and not url_conflict and job.canonical_job_url != url)
        )
        if dirty:
            job.title = cand.title
            job.employer = cand.employer
            job.location = cand.location
            job.is_remote = cand.is_remote
            if url and not url_conflict:
                job.canonical_job_url = url
            job.evidence_anchors = cand.anchors
            job.meaningful_revision += 1
            job.match_reason = match_reason or job.match_reason
            if job.status == "CLOSED":
                job.status = "NEW"
            changed += 1
            if match_reason:
                _notify_new(
                    session,
                    run.user_id,
                    job.id,
                    run.id,
                    "JOB_MATCH",
                    "UPDATED",
                    job.meaningful_revision,
                    f"Monitored job updated: {job.title}"
                    + (f" at {job.employer}" if job.employer else ""),
                )
    return changed


def _close_absent_jobs(session: Session, run: MonitoringRun, complete_since: datetime) -> None:
    """Close jobs absent from two consecutive complete scans."""
    cutoff = complete_since
    stale = session.scalars(
        select(DiscoveredJob).where(
            DiscoveredJob.user_id == run.user_id,
            DiscoveredJob.source_id == run.source_id,
            DiscoveredJob.status != "CLOSED",
            DiscoveredJob.last_seen_at < cutoff,
        )
    ).all()
    for job in stale:
        job.status = "CLOSED"
        job.meaningful_revision += 1


def begin_run(run: MonitoringRun) -> None:
    run.state = "RUNNING"
    run.started_at = datetime.now(UTC)


def record_fetch_failure(session: Session, run: MonitoringRun, exc: Exception) -> None:
    run.state = "FAILED"
    run.completeness = "UNKNOWN"
    label = "fetch_denied" if isinstance(exc, FetchDenied) else "fetch_error"
    run.redacted_error = f"{label}: {type(exc).__name__}: {exc}"[:512]
    run.ended_at = datetime.now(UTC)
    _notify_new(
        session,
        run.user_id,
        None,
        run.id,
        "SOURCE_STATUS",
        f"FAILED:{run.source_id}:{run.id}",
        1,
        f"Monitored source check failed: {type(exc).__name__}",
    )


def apply_scan_outcome(
    session: Session,
    run: MonitoringRun,
    source: MonitoredSource,
    outcome: FetchOutcome,
) -> None:
    """Diff a fetched page against stored jobs; writes jobs/notifications."""
    now = datetime.now(UTC)
    run.ended_at = now
    if outcome.status == "NOT_MODIFIED":
        run.state = "SUCCEEDED"
        run.completeness = "COMPLETE"
        run.discovered_count = 0
        source.last_success_at = now
        session.execute(
            update(DiscoveredJob)
            .where(
                DiscoveredJob.user_id == run.user_id,
                DiscoveredJob.source_id == run.source_id,
                DiscoveredJob.status != "CLOSED",
            )
            .values(last_seen_at=now)
        )
        return
    candidates, method = extract_candidates(
        outcome.content or b"",
        outcome.content_type,
        source.public_url,
        source.region_selector,
    )
    run.completed_count = len(candidates)
    changed = _upsert_candidates(session, run, candidates)
    run.discovered_count = changed
    run.state = "SUCCEEDED"
    run.completeness = "COMPLETE" if candidates or method == "feed" else "PARTIAL"
    # Closure evidence only comes from COMPLETE scans — a PARTIAL run
    # (e.g. a JS-only page yielding zero candidates) must never close jobs.
    if run.completeness == "COMPLETE":
        previous = _previous_complete_run(session, run.source_id, run.id)
        if previous is not None:
            _close_absent_jobs(session, run, previous)
    source.last_success_at = now
    if outcome.etag:
        source.last_etag = outcome.etag[:512]
    if outcome.content is not None:
        source.last_content_hash = hashlib.sha256(outcome.content).hexdigest()


def execute_monitoring_run(
    session: Session,
    run: MonitoringRun,
    source: MonitoredSource,
    fetcher: Fetcher | None = None,
) -> None:
    """Fetch, extract and diff one validated run; records an honest outcome."""
    fetcher = fetcher or Fetcher()
    begin_run(run)
    session.flush()
    try:
        outcome = fetcher.fetch(source.public_url, etag=source.last_etag)
    except (FetchDenied, FetchFailed, FetchUnsupported) as exc:
        record_fetch_failure(session, run, exc)
        return
    except Exception as exc:  # never leave the run RUNNING
        logger.exception("unexpected fetch error for run %s", run.id)
        record_fetch_failure(
            session, run, FetchFailed(f"unexpected fetch error: {type(exc).__name__}")
        )
        return
    apply_scan_outcome(session, run, source, outcome)
