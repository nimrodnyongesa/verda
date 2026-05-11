"""Preprocessing — text extraction.

Per the architecture doc this layer would integrate Whisper (audio) and
Tesseract (PDF/image OCR). The MVP runs without those binaries:
  - text/markdown/csv/json files are decoded directly
  - WhatsApp exports remain plain text
  - audio + image inputs are accepted and stored, with a stub transcript
    annotated so the lawyer knows transcription is pending

Real OCR/Whisper integration is one ``subprocess`` call away once the host
provides ``tesseract`` and ``whisper`` binaries; the rest of the pipeline does
not need to change.
"""
from __future__ import annotations

from typing import Any

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json", ".log"}
MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".log": "text/plain",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}


def detect_mime_type(filename: str) -> str:
    name = filename.lower()
    for suffix, mime in MIME_BY_SUFFIX.items():
        if name.endswith(suffix):
            return mime
    return "application/octet-stream"


def extract_text_from_bytes(filename: str, content: bytes) -> tuple[str, dict[str, Any]]:
    name = filename.lower()
    if any(name.endswith(s) for s in TEXT_SUFFIXES):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        return text, {"extraction": "decoded_utf8", "bytes": len(content)}

    if name.endswith(".pdf"):
        return _stub_pdf(filename), {"extraction": "stub_pdf", "ocr_required": True}

    if name.endswith((".jpg", ".jpeg", ".png", ".heic")):
        return _stub_image(filename), {"extraction": "stub_image", "ocr_required": True}

    if name.endswith((".mp3", ".m4a", ".wav", ".ogg")):
        return _stub_audio(filename), {"extraction": "stub_audio", "transcription_required": True}

    # Best-effort fallback: try utf-8.
    try:
        return content.decode("utf-8"), {"extraction": "best_effort_utf8"}
    except UnicodeDecodeError:
        return "", {"extraction": "binary", "bytes": len(content)}


def _stub_pdf(filename: str) -> str:
    return (
        f"[Pending OCR for {filename}]\n"
        "Once Tesseract + Vision API fallback runs against this PDF, the\n"
        "extracted text will appear here. The Codex parser already accepts\n"
        "the OCR output shape.\n"
    )


def _stub_image(filename: str) -> str:
    return (
        f"[Pending OCR for image {filename}]\n"
        "EXIF metadata is preserved on disk; the lawyer can review the file\n"
        "directly until the OCR pipeline runs.\n"
    )


def _stub_audio(filename: str) -> str:
    return (
        f"[Pending Whisper transcription for {filename}]\n"
        "Whisper-large-v3 runs with Swahili / English code-switch handling.\n"
    )
