"""Case repository — DB-shaped CRUD for cases.

This module is the canonical source of truth for case storage. Other
services compose on top of it (intake adds files, planning saves plans,
orchestrator persists runs).
"""
from __future__ import annotations

from typing import Any

from ..db import dumps_json, get_connection, loads_json, utc_now


def create_case(payload: dict[str, Any]) -> dict[str, Any] | None:
    now = utc_now()
    folder_id = payload.get("folder_id")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO cases (title, jurisdiction, legal_track, description, status, metadata_json, folder_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"].strip(),
                payload.get("jurisdiction", "ke"),
                payload.get("legal_track", "article_22_petition"),
                payload.get("description", "").strip(),
                "intake",
                dumps_json(payload.get("metadata", {})),
                folder_id,
                now,
                now,
            ),
        )
        case_id = cursor.lastrowid
    return get_case_full(case_id)


def list_cases() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM case_files cf WHERE cf.case_id = c.id) AS file_count,
                   (SELECT MAX(id) FROM generation_runs gr WHERE gr.case_id = c.id) AS latest_run_id
            FROM cases c
            ORDER BY c.updated_at DESC
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
        out.append(item)
    return out


def get_case_full(case_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            return None
        files = conn.execute(
            "SELECT * FROM case_files WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
        ).fetchall()
        plan_row = conn.execute(
            "SELECT * FROM toolkit_plans WHERE case_id = ?", (case_id,)
        ).fetchone()
        latest_run = conn.execute(
            "SELECT * FROM generation_runs WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()

    item = dict(row)
    item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
    item["files"] = [_inflate_file(f) for f in files]
    if plan_row:
        plan = loads_json(plan_row.get("plan_json"))
        plan["approved"] = bool(plan_row.get("approved"))
        plan["updated_at"] = plan_row.get("updated_at")
        item["plan"] = plan
    else:
        item["plan"] = None
    if latest_run:
        run = dict(latest_run)
        run["summary"] = loads_json(run.pop("summary_json", "{}"))
        item["latest_run"] = run
    else:
        item["latest_run"] = None
    return item


def _inflate_file(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
    item.pop("extracted_text", None)
    return item


def list_files(case_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM case_files WHERE case_id = ? ORDER BY created_at ASC",
            (case_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
        out.append(item)
    return out
