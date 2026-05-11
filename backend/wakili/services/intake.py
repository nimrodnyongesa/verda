"""Intake — receive uploaded files, deduplicate, classify, persist."""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from ..config import UPLOADS_DIR, ensure_directories
from ..db import dumps_json, get_connection, loads_json, utc_now
from ..modules.evidence_codex import classify_evidence_kind
from .audit import record_audit
from .preprocessing import detect_mime_type, extract_text_from_bytes


def add_file(case_id: int, filename: str, content: bytes, mime_type: str | None = None) -> dict[str, Any]:
    ensure_directories()
    safe_name = filename.replace("/", "_").replace("\\", "_") or "upload"
    sha = hashlib.sha256(content).hexdigest()
    stored_name = f"{case_id}_{secrets.token_hex(8)}_{safe_name}"
    path = UPLOADS_DIR / stored_name
    path.write_bytes(content)

    text, parse_meta = extract_text_from_bytes(safe_name, content)
    kind = classify_evidence_kind(safe_name, text)
    file_mime = mime_type or detect_mime_type(safe_name)
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_files (
                case_id, original_name, stored_name, mime_type, evidence_kind,
                size_bytes, sha256, extracted_text, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                safe_name,
                stored_name,
                file_mime,
                kind,
                len(content),
                sha,
                text,
                dumps_json(parse_meta),
                now,
            ),
        )
        file_id = cursor.lastrowid
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))

    record_audit(
        actor="intake",
        action="add_file",
        resource=safe_name,
        case_id=case_id,
        payload={"file_id": file_id, "kind": kind, "size": len(content), "sha256": sha},
    )
    return {
        "id": file_id,
        "case_id": case_id,
        "original_name": safe_name,
        "stored_name": stored_name,
        "mime_type": file_mime,
        "evidence_kind": kind,
        "size_bytes": len(content),
        "sha256": sha,
        "metadata": parse_meta,
        "created_at": now,
    }


def list_files(case_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM case_files WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
        out.append(item)
    return out
