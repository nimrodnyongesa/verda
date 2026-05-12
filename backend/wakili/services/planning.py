"""Planning — produce the toolkit plan that the lawyer reviews before generation.

Per architecture doc step 3, a planning agent inspects the evidence inventory
and proposes which modules to generate, which precedents to scrape, which
deadlines to track. The lawyer reviews and edits before any code is written.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..config import JURISDICTIONS_DIR
from ..db import dumps_json, get_connection, loads_json, utc_now
from ..modules.evidence_codex import build_evidence_codex
from .audit import record_audit


def _load_jurisdiction_label(jurisdiction: str, track: str) -> tuple[str, str]:
    path = JURISDICTIONS_DIR / jurisdiction / "procedural_rules.json"
    if not path.exists():
        return (track.replace("_", " ").title(), "")
    payload = json.loads(path.read_text(encoding="utf-8"))
    tracks = payload.get("tracks", {})
    entry = tracks.get(track) or next(iter(tracks.values()), {})
    return entry.get("label", track), entry.get("citation", "")


def propose_plan(case_row: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    label, citation = _load_jurisdiction_label(case_row["jurisdiction"], case_row["legal_track"])
    overview = build_evidence_codex(case_row, files)

    modules = [
        {
            "key": "evidence_codex",
            "name": "Evidence Codex (custom parser + timeline)",
            "rationale": (
                f"{overview['files_indexed']} files inspected. "
                f"{overview['events_extracted']} dated events, "
                f"{overview['officers_named']} named officers, "
                f"{overview['stations_named']} stations, "
                f"{overview['ob_numbers_seen']} OB numbers detected."
            ),
            "estimated_minutes": 18,
        },
        {
            "key": "procedural_engine",
            "name": "Procedural Engine state machine",
            "rationale": (
                f"Encodes {label}{(' (' + citation + ')') if citation else ''} as a "
                "state machine; computes deadlines and surfaces the next required filing."
            ),
            "estimated_minutes": 14,
        },
        {
            "key": "precedent_linker",
            "name": "Precedent Linker (Kenya Law)",
            "rationale": (
                "Generates a per-case ranker over kenyalaw-mcp; each cited judgment "
                "is verified by URL fetch before it appears in any draft motion."
            ),
            "estimated_minutes": 9,
        },
        {
            "key": "defender_safety_build",
            "name": "Defender Safety Build",
            "rationale": (
                "Packages the toolkit for hosted, self-hosted Docker, USB-bootable, "
                "or encrypted-bundle deployment. Telemetry off by default."
            ),
            "estimated_minutes": 6,
        },
    ]

    deadlines = _suggested_deadlines(overview)
    risks = _list_risks(overview)

    plan = {
        "case_id": case_row["id"],
        "legal_track_label": label,
        "citation": citation,
        "summary": _summary_sentence(case_row, overview),
        "modules": modules,
        "deadlines": deadlines,
        "risks": risks,
        "evidence_overview": {
            "files_indexed": overview["files_indexed"],
            "events_extracted": overview["events_extracted"],
            "issue_heatmap": overview["issue_heatmap"][:5],
            "gaps": overview["gaps"],
        },
        "approved": False,
        "generated_by": "planner.deterministic_v1",
    }
    return plan


def _summary_sentence(case_row: dict[str, Any], overview: dict[str, Any]) -> str:
    top_issues = ", ".join(item["name"] for item in overview["issue_heatmap"][:3]) or "rights affected"
    return (
        f"Proposing a {case_row['jurisdiction'].upper()} {case_row['legal_track'].replace('_', ' ')} "
        f"track focused on {top_issues}. "
        f"Built from {overview['files_indexed']} evidence file(s); "
        f"{overview['events_extracted']} timeline event(s) detected."
    )


def _suggested_deadlines(overview: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = overview.get("timeline") or []
    if not timeline:
        return []
    earliest = next((e for e in timeline if e.get("date")), None)
    if not earliest:
        return []
    iso = earliest["date"]
    base = date.fromisoformat(iso)
    return [
        {
            "label": "Article 22 petition filing target",
            "date": (base + timedelta(days=14)).isoformat(),
            "rationale": "Default 14-day window from the earliest detected incident; lawyer to confirm.",
        },
        {
            "label": "Production / habeas relief check-in",
            "date": (base + timedelta(days=2)).isoformat(),
            "rationale": "Verify whether the respondent station produced the detainees within 24 hours.",
        },
    ]


def _list_risks(overview: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if overview["gaps"]:
        risks.append(
            f"{len(overview['gaps'])} unexplained gap(s) in the evidence chronology — "
            "may indicate undocumented detention periods."
        )
    if overview["officers_named"] == 0:
        risks.append("No officers named yet — the petition will need named respondents before filing.")
    if not overview["ob_numbers_seen"]:
        risks.append("No OB numbers detected — verify whether the station refused to record the arrest.")
    if not overview["timeline"]:
        risks.append("No dates detected — Codex parser will need additional evidence types before generation.")
    return risks


def save_plan(plan: dict[str, Any]) -> None:
    case_id = plan["case_id"]
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO toolkit_plans (case_id, plan_json, approved, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                plan_json = excluded.plan_json,
                approved = excluded.approved,
                updated_at = excluded.updated_at
            """,
            (case_id, dumps_json(plan), int(plan.get("approved", False)), now, now),
        )
    record_audit(
        actor="planner",
        action="save_plan",
        case_id=case_id,
        resource="toolkit_plan",
        payload={"approved": plan.get("approved", False), "modules": [m["key"] for m in plan["modules"]]},
    )


def load_plan(case_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM toolkit_plans WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        return None
    plan = loads_json(row.get("plan_json"))
    plan["approved"] = bool(row.get("approved"))
    plan["updated_at"] = row.get("updated_at")
    return plan


def approve_plan(case_id: int) -> dict[str, Any] | None:
    plan = load_plan(case_id)
    if not plan:
        return None
    plan["approved"] = True
    save_plan(plan)
    record_audit(actor="lawyer", action="approve_plan", case_id=case_id, resource="toolkit_plan")
    return plan
