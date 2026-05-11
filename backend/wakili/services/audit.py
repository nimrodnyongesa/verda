"""Audit log — every MCP call, every Codex prompt, every export is recorded."""
from __future__ import annotations

from typing import Any

from ..db import dumps_json, get_connection, loads_json, utc_now


def record_audit(
    *,
    actor: str,
    action: str,
    resource: str = "",
    payload: dict[str, Any] | None = None,
    case_id: int | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (case_id, actor, action, resource, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (case_id, actor, action, resource, dumps_json(payload or {}), utc_now()),
        )


def list_audit(case_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if case_id is None:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE case_id = ? OR case_id IS NULL ORDER BY id DESC LIMIT ?",
                (case_id, limit),
            ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["payload"] = loads_json(item.pop("payload_json", "{}"))
        out.append(item)
    return out
