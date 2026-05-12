"""Document exporter — turn drafted motions / petitions into DOCX + PDF.

Constraints:
  * No external runtime deps. The user installs Verda from
    ``backend/requirements.txt`` (FastAPI, pydantic, PyJWT, cryptography,
    mcp). We do NOT add reportlab / python-docx — both formats are
    written from scratch by hand using stdlib only (zipfile, io, struct).
  * Every ``{{placeholder}}`` token left over in the raw markdown is
    aggressively rewritten before export, so a download never ships
    "{{petitioner_block}}" through to the lawyer. Any unresolved tokens
    become "[TO BE COMPLETED BEFORE FILING]" so the lawyer-in-the-loop
    boundary is visible.
  * Petition / motion text in the body is plain ASCII; non-ASCII
    characters are mapped to safe equivalents in the PDF path (the
    minimal PDF engine here uses Helvetica / WinAnsiEncoding).

Both exporters render the *resolved* markdown (no template tokens). They
deliberately use a simple block layout: H1 / H2 / paragraph / list.
That keeps the PDF/DOCX output compatible with Google Drive's
"open with → Google Docs" auto-import path that the user wants.
"""
from __future__ import annotations

import io
import re
import struct
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator
from xml.sax.saxutils import escape as xml_escape


PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\-.]+)\s*\}\}")
SQUARE_PLACEHOLDER_RE = re.compile(r"\[\s*[A-Z][A-Z0-9 _\-/.,'·]*\]")


def resolve_placeholders(content: str, *, fallback: str = "[TO BE COMPLETED BEFORE FILING]") -> str:
    """Replace any unresolved ``{{token}}`` with ``fallback``.

    The procedural-engine renderer fills every known token, but a
    template change can leave dangling tokens behind. This pass
    guarantees a clean download — the lawyer never sees raw
    placeholder syntax in a file they intend to edit and sign.
    """
    return PLACEHOLDER_RE.sub(fallback, content)


# ---------------------------------------------------------------------------
# Lightweight markdown → block list. We don't aim at full CommonMark — the
# templates Verda ships use a small, predictable subset.
# ---------------------------------------------------------------------------


@dataclass
class Block:
    kind: str  # "h1" | "h2" | "h3" | "p" | "li" | "blank" | "code"
    text: str


def _parse_blocks(md: str) -> list[Block]:
    blocks: list[Block] = []
    in_code = False
    code_buf: list[str] = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                blocks.append(Block("code", "\n".join(code_buf)))
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(raw)
            continue
        if not line.strip():
            blocks.append(Block("blank", ""))
            continue
        if line.startswith("# "):
            blocks.append(Block("h1", line[2:].strip()))
        elif line.startswith("## "):
            blocks.append(Block("h2", line[3:].strip()))
        elif line.startswith("### "):
            blocks.append(Block("h3", line[4:].strip()))
        elif re.match(r"^\s*[-*]\s+", line):
            blocks.append(Block("li", re.sub(r"^\s*[-*]\s+", "", line)))
        elif re.match(r"^\s*\d+\.\s+", line):
            blocks.append(Block("li", re.sub(r"^\s*\d+\.\s+", "", line)))
        else:
            # Append to previous paragraph if it's mid-paragraph; otherwise new.
            if blocks and blocks[-1].kind == "p":
                blocks[-1] = Block("p", blocks[-1].text + " " + line.strip())
            else:
                blocks.append(Block("p", line.strip()))
    if in_code:
        blocks.append(Block("code", "\n".join(code_buf)))
    return blocks


def _strip_md_inline(text: str) -> str:
    """Remove **bold** / *italic* markers — neither path supports rich
    inline runs in the minimal export, so we render text-only and rely on
    structural elements (headings, lists) for visual hierarchy."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# DOCX — Office Open XML, minimal but valid. Produces a .docx that
# Google Drive auto-converts to a Google Doc on upload, and that Word
# / LibreOffice / Pages open without complaint.
# ---------------------------------------------------------------------------


def _docx_paragraph(style: str | None, runs: list[str]) -> str:
    style_xml = f"<w:pStyle w:val=\"{style}\"/>" if style else ""
    body = "".join(
        f'<w:r><w:t xml:space="preserve">{xml_escape(run)}</w:t></w:r>'
        for run in runs
    )
    return f"<w:p><w:pPr>{style_xml}</w:pPr>{body}</w:p>"


def _docx_list_paragraph(text: str) -> str:
    # Single-level bullet via Word's standard "ListParagraph" style and a
    # bullet character. Avoids the numbering.xml part to keep this writer
    # tiny.
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:ind w:left="720" w:hanging="360"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">• </w:t></w:r>'
        f'<w:r><w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p>'
    )


def _docx_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/><w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/><w:qFormat/>
  </w:style>
</w:styles>"""


def _docx_document_xml(blocks: list[Block]) -> str:
    parts: list[str] = []
    for b in blocks:
        text = _strip_md_inline(b.text)
        if b.kind == "h1":
            parts.append(_docx_paragraph("Heading1", [text]))
        elif b.kind == "h2":
            parts.append(_docx_paragraph("Heading2", [text]))
        elif b.kind == "h3":
            parts.append(_docx_paragraph("Heading3", [text]))
        elif b.kind == "li":
            parts.append(_docx_list_paragraph(text))
        elif b.kind == "code":
            for line in (text or "").splitlines() or [""]:
                parts.append(_docx_paragraph(None, [line]))
        elif b.kind == "blank":
            parts.append(_docx_paragraph(None, [""]))
        else:
            parts.append(_docx_paragraph(None, [text]))
    body = "".join(parts)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body>
</w:document>"""


def render_docx(markdown_text: str) -> bytes:
    """Return a .docx blob (Office Open XML) that Word / Drive accept."""
    resolved = resolve_placeholders(markdown_text)
    blocks = _parse_blocks(resolved)
    document_xml = _docx_document_xml(blocks)
    styles_xml = _docx_styles_xml()
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
    rels_root = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    rels_doc = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels_root)
        z.writestr("word/_rels/document.xml.rels", rels_doc)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/styles.xml", styles_xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF — minimal hand-rolled engine. One Helvetica font, blocks laid out
# line-by-line with simple word wrapping. Output passes Adobe Reader,
# Preview, Chrome, and Drive auto-import. No external deps.
# ---------------------------------------------------------------------------


PAGE_WIDTH_PT = 612          # US Letter
PAGE_HEIGHT_PT = 792
MARGIN_PT = 72               # 1 inch
LINE_HEIGHT_PT = 14
HEADING_LINE_HEIGHT_PT = {
    "h1": 28,
    "h2": 22,
    "h3": 18,
    "p": 14,
    "li": 14,
    "code": 13,
    "blank": 8,
}
FONT_SIZE = {
    "h1": 18,
    "h2": 14,
    "h3": 12,
    "p": 11,
    "li": 11,
    "code": 10,
    "blank": 11,
}
# Width per character at the given font size (rough Helvetica avg width ≈ 0.5em).
CHAR_WIDTH_FACTOR = 0.5


def _pdf_escape(text: str) -> str:
    text = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    # Strip non-ASCII to keep PDF body in WinAnsi range without an embedded font.
    text = "".join(c if ord(c) < 128 else "?" for c in text)
    return text


def _wrap(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip() if current else w
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            # Hard-wrap a giant word.
            while len(w) > max_chars:
                lines.append(w[:max_chars])
                w = w[max_chars:]
            current = w
    if current:
        lines.append(current)
    return lines


_TYPO: dict[str, tuple[str, int, int]] = {
    # kind -> (font_id, size_pt, line_height_pt)
    "h1": ("F1B", 18, 28),
    "h2": ("F1B", 14, 22),
    "h3": ("F1B", 12, 18),
    "p":  ("F1", 11, 14),
    "li": ("F1", 11, 14),
    "code": ("F2", 10, 13),
    "blank": ("F1", 11, 8),
}


def render_pdf(markdown_text: str, *, title: str = "Verda export") -> bytes:
    """Render the resolved markdown to a single-document PDF byte stream.

    Wrapped in a top-level try/except so any rendering bug surfaces as a
    short, valid PDF carrying the error message rather than a 500. That
    guarantees the user always gets a downloadable artefact even when the
    upstream content is malformed — they can tell counsel "the PDF
    download said X" instead of seeing an opaque browser error.
    """
    try:
        return _render_pdf_impl(markdown_text, title=title)
    except Exception as exc:  # noqa: BLE001 — last-ditch resilience
        return _render_minimal_pdf(
            "Verda — PDF render failed\n\n"
            f"This document could not be rendered as a PDF. The error was:\n\n"
            f"  {type(exc).__name__}: {exc}\n\n"
            "Re-run generation, or download the .docx / .md alternative — "
            "those use a different renderer and may succeed."
        )


def _render_pdf_impl(markdown_text: str, *, title: str = "Verda export") -> bytes:
    """Concrete renderer.

    Pagination model: we walk the parsed blocks, expanding each one into
    one or more wrapped lines that carry their own line-height (so the
    writer never has to guess by re-keying typography). When a line would
    cross the bottom margin a new page starts. Empty / blank-line entries
    use the kind's own line-height (e.g. 8 pt for "blank") so vertical
    rhythm is preserved.
    """
    resolved = resolve_placeholders(markdown_text)
    blocks = _parse_blocks(resolved)

    # ---- Build a flat list of (font, size, line_h, text) lines -----------
    lines: list[tuple[str, int, int, str]] = []
    usable_width_pt = PAGE_WIDTH_PT - 2 * MARGIN_PT
    for b in blocks:
        font, size, line_h = _TYPO.get(b.kind, _TYPO["p"])
        max_chars = max(8, int(usable_width_pt / max(1.0, size * CHAR_WIDTH_FACTOR)))
        if b.kind == "blank":
            lines.append((font, size, line_h, ""))
            continue
        text = _strip_md_inline(b.text or "")
        if b.kind == "li":
            text = "• " + text
        if b.kind == "code":
            for raw in (text or "").splitlines() or [""]:
                lines.append((font, size, line_h, raw))
            continue
        for wrapped in _wrap(text, max_chars):
            lines.append((font, size, line_h, wrapped))

    # ---- Paginate --------------------------------------------------------
    pages: list[list[tuple[str, int, int, str]]] = [[]]
    remaining = PAGE_HEIGHT_PT - 2 * MARGIN_PT
    for entry in lines:
        _, _, line_h, _ = entry
        if line_h > remaining and pages[-1]:
            pages.append([])
            remaining = PAGE_HEIGHT_PT - 2 * MARGIN_PT
        pages[-1].append(entry)
        remaining -= line_h
    if pages == [[]]:
        # Empty input — emit a single blank page so the file is valid.
        pages = [[("F1", 11, 14, "")]]

    # ---- Object stream ---------------------------------------------------
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []  # 0-indexed byte offsets, parallel to obj-id-1

    def write_obj(obj_id: int, body: bytes) -> None:
        # Pad offsets list to obj_id — we may write objects out of declared
        # order, so the list is sparse until xref time.
        while len(offsets) < obj_id:
            offsets.append(0)
        offsets[obj_id - 1] = out.tell()
        out.write(f"{obj_id} 0 obj\n".encode() + body + b"\nendobj\n")

    # Reserved IDs — declare the referenced objects up-front so cross-refs
    # in the page stream (which is written first) point at known IDs.
    catalog_id = 1
    pages_id = 2
    font_regular_id = 3
    font_bold_id = 4
    font_mono_id = 5
    next_id = 6

    page_obj_ids: list[int] = []
    for page_lines in pages:
        # Build the content stream.
        stream = io.BytesIO()
        stream.write(b"BT\n")
        y = PAGE_HEIGHT_PT - MARGIN_PT
        last_font: str | None = None
        last_size: int | None = None
        first = True
        for font, size, line_h, text in page_lines:
            if first:
                stream.write(f"/{font} {size} Tf\n".encode())
                stream.write(f"1 0 0 1 {MARGIN_PT} {y} Tm\n".encode())
                last_font, last_size = font, size
                first = False
            else:
                if (font, size) != (last_font, last_size):
                    stream.write(f"/{font} {size} Tf\n".encode())
                    last_font, last_size = font, size
                stream.write(f"0 -{line_h} Td\n".encode())
            esc = _pdf_escape(text)
            stream.write(f"({esc}) Tj\n".encode())
        stream.write(b"ET\n")
        body = stream.getvalue()

        content_id = next_id
        next_id += 1
        write_obj(
            content_id,
            f"<< /Length {len(body)} >>\nstream\n".encode() + body + b"\nendstream",
        )

        page_id = next_id
        next_id += 1
        write_obj(
            page_id,
            (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH_PT} {PAGE_HEIGHT_PT}] "
                f"/Contents {content_id} 0 R "
                f"/Resources << /Font << "
                f"/F1 {font_regular_id} 0 R "
                f"/F1B {font_bold_id} 0 R "
                f"/F2 {font_mono_id} 0 R "
                f">> >> >>"
            ).encode(),
        )
        page_obj_ids.append(page_id)

    # Reserved IDs — write at known offsets.
    write_obj(
        catalog_id,
        f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode(),
    )
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    write_obj(
        pages_id,
        f"<< /Type /Pages /Count {len(page_obj_ids)} /Kids [{kids}] >>".encode(),
    )
    write_obj(
        font_regular_id,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    )
    write_obj(
        font_bold_id,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    )
    write_obj(
        font_mono_id,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    )

    # xref + trailer
    xref_offset = out.tell()
    object_count = len(offsets) + 1  # +1 for the free entry at index 0
    out.write(f"xref\n0 {object_count}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {object_count} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return out.getvalue()


def _render_minimal_pdf(message: str) -> bytes:
    """Produce a single-page valid PDF carrying ``message`` as plain text.

    Used as the last-ditch fallback when ``_render_pdf_impl`` raises so a
    download attempt always returns something valid. This path is
    deliberately byte-tiny and dependency-free.
    """
    body = io.BytesIO()
    body.write(b"BT\n/F1 11 Tf\n")
    body.write(f"1 0 0 1 {MARGIN_PT} {PAGE_HEIGHT_PT - MARGIN_PT} Tm\n".encode())
    first = True
    for line in message.splitlines() or [""]:
        if first:
            first = False
        else:
            body.write(b"0 -14 Td\n")
        for sub in _wrap(line, 80):
            body.write(f"({_pdf_escape(sub)}) Tj\n0 -14 Td\n".encode())
    body.write(b"ET\n")
    stream = body.getvalue()

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    def write_obj(obj_id: int, b: bytes) -> None:
        while len(offsets) < obj_id:
            offsets.append(0)
        offsets[obj_id - 1] = out.tell()
        out.write(f"{obj_id} 0 obj\n".encode() + b + b"\nendobj\n")

    write_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    write_obj(2, b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>")
    write_obj(
        3,
        f"<< /Type /Page /Parent 2 0 R "
        f"/MediaBox [0 0 {PAGE_WIDTH_PT} {PAGE_HEIGHT_PT}] "
        f"/Contents 4 0 R "
        f"/Resources << /Font << /F1 5 0 R >> >> >>".encode(),
    )
    write_obj(
        4,
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    )
    write_obj(
        5,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    )

    xref_offset = out.tell()
    object_count = len(offsets) + 1
    out.write(f"xref\n0 {object_count}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {object_count} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return out.getvalue()


__all__ = ["resolve_placeholders", "render_docx", "render_pdf"]
