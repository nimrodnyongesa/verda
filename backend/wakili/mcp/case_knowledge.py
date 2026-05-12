"""case-knowledge-mcp — structured query over a case's evidence inventory.

Allows the planner / generation agents to ask, e.g., "what dates appear in this
case?" or "list all officers named in OB extracts" without re-running the full
parser. Reads from the case's stored evidence rows.
"""
from __future__ import annotations

from typing import Any

from ..db import get_connection, loads_json
from ..services.audit import record_audit


def list_evidence(case_id: int) -> list[dict[str, Any]]:
    record_audit(
        actor="case-knowledge-mcp",
        action="list_evidence",
        resource=f"case={case_id}",
        payload={"case_id": case_id},
        case_id=case_id,
    )
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, original_name, evidence_kind, mime_type, size_bytes, sha256, metadata_json, created_at "
            "FROM case_files WHERE case_id = ? ORDER BY created_at ASC",
            (case_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
        out.append(item)
    return out


def get_evidence_text(case_id: int, file_id: int) -> str:
    record_audit(
        actor="case-knowledge-mcp",
        action="get_evidence_text",
        resource=f"case={case_id};file={file_id}",
        payload={"case_id": case_id, "file_id": file_id},
        case_id=case_id,
    )
    with get_connection() as conn:
        row = conn.execute(
            "SELECT extracted_text FROM case_files WHERE case_id = ? AND id = ?",
            (case_id, file_id),
        ).fetchone()
    return (row or {}).get("extracted_text", "") if row else ""
