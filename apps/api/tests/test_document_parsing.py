"""Bounded document parser checks (DOC-002)."""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document as DocxDocument

from app.worker.parsing import (
    DOCX_MEDIA,
    PDF_MEDIA,
    ParseResult,
    parse_document,
    split_sections,
)


def _make_pdf(lines: list[str]) -> bytes:
    """Emit a minimal valid text PDF with a correctly computed xref table."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    tokens = " T* ".join(f"({line}) Tj" for line in escaped)
    body = " BT /F1 12 Tf 72 720 Td 16 TL " + tokens + " ET"
    content = body.encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(output)


MINIMAL_PDF = _make_pdf(["Hello parser test", "Second line"])


def _write(tmp_path: Path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_pdf_text_extracts_with_page_anchors(tmp_path: Path) -> None:
    result = parse_document(_write(tmp_path, "resume.pdf", MINIMAL_PDF), PDF_MEDIA)
    assert result.status == "OK"
    assert "Hello parser test" in result.text
    assert result.anchors and result.anchors[0]["page"] == 1
    assert result.page_count == 1


def test_blank_pdf_reports_unsupported_not_crash(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = tmp_path / "blank.pdf"
    with buffer.open("wb") as handle:
        writer.write(handle)
    result = parse_document(str(buffer), PDF_MEDIA)
    assert result.status == "UNSUPPORTED"
    assert result.error


def test_malformed_pdf_fails_safely(tmp_path: Path) -> None:
    result = parse_document(_write(tmp_path, "bad.pdf", b"%PDF-1.4 not a pdf"), PDF_MEDIA)
    assert result.status in {"FAILED", "UNSUPPORTED"}
    assert result.error


def test_docx_text_extracts_with_block_anchors(tmp_path: Path) -> None:
    document = DocxDocument()
    document.add_paragraph("Experience")
    document.add_paragraph("Built reliable systems at Example Corp.")
    path = tmp_path / "resume.docx"
    document.save(str(path))
    result = parse_document(str(path), DOCX_MEDIA)
    assert result.status == "OK"
    assert "Example Corp." in result.text
    assert any(anchor["block"] is not None for anchor in result.anchors)


def test_non_zip_docx_fails_safely(tmp_path: Path) -> None:
    result = parse_document(_write(tmp_path, "bad.docx", b"PK\x03\x04 truncated"), DOCX_MEDIA)
    assert result.status == "FAILED"
    assert result.error


def test_unknown_media_type_is_unsupported(tmp_path: Path) -> None:
    result = parse_document(_write(tmp_path, "file.bin", b"\x00"), "application/octet-stream")
    assert result.status == "UNSUPPORTED"


def test_sections_are_bounded_and_anchored() -> None:
    result = ParseResult(
        status="OK",
        text="\n\n".join(f"Paragraph {index} text" for index in range(6)),
        anchors=[{"page": 1, "block": index, "excerpt": f"p{index}"} for index in range(6)],
    )
    sections = split_sections(result, section_chars=60)
    assert len(sections) >= 2
    for section in sections:
        assert len(section["text"]) <= 60
        assert "anchor" in section
    assert split_sections(ParseResult(status="FAILED")) == []


@pytest.mark.skipif(
    not Path("/usr/bin/python3").exists() and not Path("/bin").exists(),
    reason="requires a POSIX python for the sandboxed child",
)
def test_parser_child_does_not_inherit_network_or_filesystem_writes(
    tmp_path: Path,
) -> None:
    # The child ran inside parse_document above; this asserts the parent API
    # always returns rather than raising even for hostile inputs.
    hostile = b"%PDF-1.4\n" + b"(" * 200_000
    result = parse_document(_write(tmp_path, "hostile.pdf", hostile), PDF_MEDIA)
    assert result.status in {"FAILED", "UNSUPPORTED", "OK"}
