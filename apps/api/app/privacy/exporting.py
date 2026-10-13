"""Export v2 ZIP assembly (DATA-002).

The archive carries a manifest with schema version, generation time,
timezone and per-file SHA-256 checksums; profile/fact/candidate data;
application, evidence and answer records as JSON and CSV; email drafts;
monitoring sources/runs/jobs/notifications; usage, audit and routing
preferences; and original document blobs. It never includes key material,
credential ciphertext/wrapped DEKs, sessions, tokens, or secret
transaction data. CSV cells are formula-escaped and member names are
fixed safe ASCII paths.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document

EXPORT_SCHEMA_VERSION = 2
MAX_ORIGINAL_BYTES = 50 * 1024 * 1024
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_SKIP_COLUMNS = {
    "ciphertext",
    "nonce",
    "wrapped_dek",
    "kek_version",
    "key_last4",
    "token_hash",
    "verifier_ciphertext",
    "nonce_hash",
    "state_hash",
    "session_digest",
    "actor_hash",
    "user_id_hash",
    "entity_ref_hash",
    "integrity_hmac",
    "revoked_session_digest",
    "encrypted_cleanup_payload",
    "result_storage_key",
    "storage_key",
    "sha256",
    "lease_owner",
    "authorization",
    "cookie",
}


def _csv_safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        text = "'" + text
    return text


def _rows(session: Session, table: str, user_id: UUID) -> list[dict[str, Any]]:
    # Table names are the hardcoded export set below; user_id is bound.
    result = session.execute(
        sa.text(f'SELECT * FROM "{table}" WHERE user_id = :owner'),
        {"owner": user_id},
    )
    rows: list[dict[str, Any]] = []
    for row in result:
        record: dict[str, Any] = {}
        for name, value in row._mapping.items():
            if name in _SKIP_COLUMNS:
                continue
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, UUID):
                value = str(value)
            elif isinstance(value, bytes):
                value = f"<bytes:{len(value)}>"
            record[name] = value
        rows.append(record)
    return rows


def _to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    keys = sorted({key for row in rows for key in row})
    writer = csv.writer(buffer)
    writer.writerow(keys)
    for row in rows:
        writer.writerow([_csv_safe(row.get(key)) for key in keys])
    return buffer.getvalue()


def build_export_zip(
    session: Session,
    user_id: UUID,
    blob_getter: Callable[[str], bytes] | None = None,
) -> tuple[bytes, dict[str, str]]:
    """Assemble the export ZIP inside the owner-scoped session.

    Returns (zip_bytes, checksums) where checksums maps member name to
    SHA-256 hex. All data is read under the caller's owner transaction.
    """
    timezone = session.scalar(
        sa.text("SELECT timezone FROM copilot_current_user LIMIT 1")
    ) or "UTC"
    tables: dict[str, list[dict[str, Any]]] = {
        name: _rows(session, table, user_id)
        for name, table in (
            ("profile", "profiles"),
            ("profile_facts", "profile_facts"),
            ("profile_fact_versions", "profile_fact_versions"),
            ("documents", "documents"),
            ("document_extractions", "document_extractions"),
            ("provider_settings", "provider_settings"),
            ("provider_routes", "provider_routes"),
            ("application_sessions", "application_sessions"),
            ("applications", "applications"),
            ("submission_events", "submission_events"),
            ("application_status_events", "application_status_events"),
            ("application_answers", "application_answers"),
            ("email_drafts", "email_drafts"),
            ("monitored_sources", "monitored_sources"),
            ("monitoring_runs", "monitoring_runs"),
            ("discovered_jobs", "discovered_jobs"),
            ("notifications", "notifications"),
            ("audit_events", "audit_events"),
        )
    }
    originals: dict[str, bytes] = {}
    if blob_getter is not None:
        original_bytes = 0
        documents = session.scalars(
            select(Document).where(
                Document.user_id == user_id,
                Document.original_state == "READY",
            )
        ).all()
        for document in documents:
            try:
                blob = blob_getter(document.storage_key)
            except Exception:
                continue
            original_bytes += len(blob)
            if original_bytes > MAX_ORIGINAL_BYTES:
                break
            safe_name = "".join(
                char if char.isalnum() or char in "._-" else "_"
                for char in (document.file_name or "document")
            )[:200]
            originals[f"originals/{document.id}_{safe_name}"] = blob
    return _assemble_zip(tables, originals, str(timezone))


def _assemble_zip(
    tables: dict[str, list[dict[str, Any]]],
    originals: dict[str, bytes],
    timezone: str,
) -> tuple[bytes, dict[str, str]]:
    members: dict[str, bytes] = {}
    for name, rows in tables.items():
        clean = [
            {key: value for key, value in row.items() if key not in _SKIP_COLUMNS}
            for row in rows
        ]
        members[f"data/{name}.json"] = json.dumps(
            clean, ensure_ascii=False, indent=1, default=str
        ).encode()
        csv_text = _to_csv(clean)
        if csv_text:
            members[f"data/{name}.csv"] = csv_text.encode()
    members.update(originals)

    checksums = {
        name: hashlib.sha256(content).hexdigest() for name, content in members.items()
    }
    manifest = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "timezone": timezone,
        "checksums": checksums,
    }
    members["manifest.json"] = json.dumps(manifest, indent=1).encode()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    return buffer.getvalue(), checksums
