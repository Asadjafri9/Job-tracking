"""Unit checks for export ZIP safety: CSV formulas, secrets, checksums (DATA-002)."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

from app.privacy.exporting import (
    EXPORT_SCHEMA_VERSION,
    _assemble_zip,
    _csv_safe,
    _to_csv,
)


def test_csv_safe_escapes_formula_prefixes() -> None:
    for hostile in ("=1+1", "+cmd", "-2-3", "@SUM(1)", "\t=1", "\rx"):
        assert _csv_safe(hostile).startswith("'")
    assert _csv_safe("normal value") == "normal value"
    assert _csv_safe(None) == ""
    assert _csv_safe(42) == "42"


def test_to_csv_serializes_structures_and_escapes_cells() -> None:
    csv_text = _to_csv([{"a": "=1+1", "b": {"x": 1}}])
    lines = csv_text.strip().split("\r\n")
    assert lines[0] == "a,b"
    assert lines[1].startswith("'=1+1,")
    assert '"{""x"": 1}"' in lines[1]


def test_assemble_zip_has_manifest_checksums_and_safe_names() -> None:
    tables = {
        "profile_facts": [
            {"id": "1", "field": "name", "value": "Ada", "ciphertext": b"xx"}
        ]
    }
    zip_bytes, checksums = _assemble_zip(
        tables, {"originals/doc_resume.pdf": b"%PDF-fake"}, "UTC"
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        assert all(
            name.replace("_", "").replace("-", "").replace("/", "").replace(
                ".", ""
            ).isalnum()
            for name in names
        )
        assert "data/profile_facts.json" in names
        assert "data/profile_facts.csv" in names
        assert "originals/doc_resume.pdf" in names
        manifest = json.loads(archive.read("manifest.json"))
        rows = json.loads(archive.read("data/profile_facts.json"))

    assert manifest["schema_version"] == EXPORT_SCHEMA_VERSION
    assert manifest["timezone"] == "UTC"
    for name, digest in manifest["checksums"].items():
        assert name != "manifest.json"
        assert digest == checksums[name]
    # Assembly defensively drops secret-shaped columns even if a caller
    # forgets the _rows deny-list.
    assert "ciphertext" not in rows[0]


def test_assemble_zip_checksums_match_member_content() -> None:
    zip_bytes, checksums = _assemble_zip({"a": [{"x": 1}]}, {}, "UTC")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name, digest in checksums.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_rows_skips_secret_columns() -> None:
    # _SKIP_COLUMNS is applied inside _rows; pin the deny-list so new secret
    # columns cannot silently leak into exports.
    from app.privacy.exporting import _SKIP_COLUMNS

    assert {
        "ciphertext",
        "nonce",
        "wrapped_dek",
        "kek_version",
        "key_last4",
        "token_hash",
        "verifier_ciphertext",
        "nonce_hash",
        "integrity_hmac",
        "encrypted_cleanup_payload",
        "storage_key",
        "lease_owner",
    } <= _SKIP_COLUMNS
