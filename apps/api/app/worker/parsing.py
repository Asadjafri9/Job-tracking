"""Bounded document text extraction (DOC-002).

Extraction always runs in a fresh subprocess with POSIX resource limits: the
worker only sees a bounded JSON result. Malformed, encrypted, oversized or
scanned inputs return an explicit status instead of crashing the worker.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PARSE_VERSION = "parser-v1"
MAX_PAGES = 50
MAX_EXTRACTED_CHARS = 100_000
MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_EXPANDED_BYTES = 25 * 1024 * 1024
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
CPU_LIMIT_SECONDS = 15
WALL_LIMIT_SECONDS = 15
MAX_RESULT_BYTES = 2 * 1024 * 1024
PDF_MEDIA = "application/pdf"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ParseStatus = Literal["OK", "UNSUPPORTED", "FAILED"]


@dataclass
class ParseResult:
    status: ParseStatus
    text: str = ""
    anchors: list[dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    error: str | None = None


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    # macOS rejects address-space/data limits below the interpreter's
    # already-mapped usage; POSIX systems enforce the 256 MiB bound while
    # Darwin relies on the in-code expansion/character caps below.
    if hasattr(resource, "RLIMIT_AS") and sys.platform != "darwin":
        resource.setrlimit(
            resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES)
        )
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _extract_pdf(path: str) -> ParseResult:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(path, strict=False)
    except (PdfReadError, OSError, ValueError):
        return ParseResult(status="FAILED", error="document could not be read")
    if reader.is_encrypted:
        return ParseResult(status="UNSUPPORTED", error="password-protected document")
    pages = len(reader.pages)
    if pages > MAX_PAGES:
        return ParseResult(status="FAILED", error="document exceeds the page limit")
    text_parts: list[str] = []
    anchors: list[dict[str, Any]] = []
    total = 0
    for index in range(pages):
        try:
            page_text = reader.pages[index].extract_text() or ""
        except Exception:  # pypdf raises arbitrary errors on malformed pages
            page_text = ""
        page_text = page_text.strip()
        if not page_text:
            continue
        remaining = MAX_EXTRACTED_CHARS - total
        if remaining <= 0:
            break
        clipped = page_text[:remaining]
        anchors.append({"page": index + 1, "block": 0, "excerpt": clipped[:200]})
        text_parts.append(clipped)
        total += len(clipped)
    text = "\n\n".join(text_parts).strip()
    if not text:
        return ParseResult(status="UNSUPPORTED", error="no extractable text (scanned?)")
    return ParseResult(status="OK", text=text, anchors=anchors, page_count=pages)


def _check_zip_bounds(path: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                return "document package exceeds the entry limit"
            if sum(info.file_size for info in infos) > MAX_ZIP_EXPANDED_BYTES:
                return "document package exceeds the expansion limit"
    except zipfile.BadZipFile:
        return "document package is malformed"
    return None


def _extract_docx(path: str) -> ParseResult:
    from docx import Document as DocxDocument

    zip_error = _check_zip_bounds(path)
    if zip_error:
        return ParseResult(status="FAILED", error=zip_error)
    try:
        document = DocxDocument(path)
    except Exception:
        return ParseResult(status="FAILED", error="document could not be read")
    text_parts: list[str] = []
    anchors: list[dict[str, Any]] = []
    total = 0
    for block, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        remaining = MAX_EXTRACTED_CHARS - total
        if remaining <= 0:
            break
        clipped = text[:remaining]
        anchors.append({"page": None, "block": block, "excerpt": clipped[:200]})
        text_parts.append(clipped)
        total += len(clipped)
    text = "\n\n".join(text_parts).strip()
    if not text:
        return ParseResult(status="UNSUPPORTED", error="no extractable text")
    return ParseResult(status="OK", text=text, anchors=anchors, page_count=0)


def _extract(path: str, media_type: str) -> ParseResult:
    if media_type == PDF_MEDIA:
        return _extract_pdf(path)
    if media_type == DOCX_MEDIA:
        return _extract_docx(path)
    return ParseResult(status="UNSUPPORTED", error="unsupported media type")


def parse_document(path: str, media_type: str) -> ParseResult:
    """Run extraction in a resource-limited child process; never raises."""
    command = [
        sys.executable,
        "-m",
        "app.worker.parsing",
        "child",
        path,
        media_type,
    ]
    package_root = str(Path(__file__).resolve().parents[2])
    environment = dict(os.environ)
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{package_root}{os.pathsep}{python_path}" if python_path else package_root
    )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=WALL_LIMIT_SECONDS,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return ParseResult(status="FAILED", error="parser exceeded the time limit")
    except OSError:
        return ParseResult(status="FAILED", error="parser process could not start")
    stdout = completed.stdout[:MAX_RESULT_BYTES]
    if completed.returncode != 0:
        return ParseResult(status="FAILED", error="parser process failed")
    try:
        payload = json.loads(stdout)
        return ParseResult(
            status=payload["status"],
            text=payload.get("text", "")[:MAX_EXTRACTED_CHARS],
            anchors=list(payload.get("anchors", []))[:500],
            page_count=int(payload.get("page_count", 0)),
            error=payload.get("error"),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return ParseResult(status="FAILED", error="parser returned an invalid result")


def split_sections(result: ParseResult, *, section_chars: int = 2_000) -> list[dict[str, Any]]:
    """Group extracted text into bounded anchored sections for provider input."""
    if result.status != "OK" or not result.text:
        return []
    paragraphs = result.text.split("\n\n")
    anchor_index = 0
    sections: list[dict[str, Any]] = []
    current: list[str] = []
    current_anchor: dict[str, Any] = {}
    section_id = 0
    for paragraph in paragraphs:
        anchor = result.anchors[anchor_index] if anchor_index < len(result.anchors) else {}
        if current and sum(len(part) for part in current) + len(paragraph) > section_chars:
            sections.append(
                {
                    "section_id": section_id,
                    "heading": "",
                    "anchor": {
                        "page": current_anchor.get("page"),
                        "block": current_anchor.get("block"),
                        "excerpt": (current_anchor.get("excerpt") or "")[:200],
                    },
                    "text": "\n\n".join(current)[:section_chars],
                }
            )
            section_id += 1
            current = []
            current_anchor = {}
        if not current_anchor:
            current_anchor = anchor
        current.append(paragraph)
        anchor_index += 1
    if current:
        sections.append(
            {
                "section_id": section_id,
                "heading": "",
                "anchor": {
                    "page": current_anchor.get("page"),
                    "block": current_anchor.get("block"),
                    "excerpt": (current_anchor.get("excerpt") or "")[:200],
                },
                "text": "\n\n".join(current)[:section_chars],
            }
        )
    return sections[:200]


def _child_main(argv: list[str]) -> int:
    _child_limits()
    path, media_type = argv[0], argv[1]
    result = _extract(path, media_type)
    sys.stdout.write(
        json.dumps(
            {
                "status": result.status,
                "text": result.text,
                "anchors": result.anchors,
                "page_count": result.page_count,
                "error": result.error,
            }
        )
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "child":
        raise SystemExit(_child_main(sys.argv[2:]))
    if len(sys.argv) >= 3:
        outcome = parse_document(sys.argv[1], sys.argv[2])
        sys.stdout.write(json.dumps(outcome.__dict__))
        raise SystemExit(0)
    raise SystemExit(2)
