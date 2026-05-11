"""Orchestrator — runs the per-case toolkit generation pipeline.

Records a generation_run + a stream of generation_events that the frontend
can replay (per the demo plan §3 and §4 — pre-baked Codex run replayed at
6–10× speed). Each event has a delay_ms so the UI can pace playback.
"""
from __future__ import annotations

import time
from typing import Any

from ..adapters.codex_replay import codex_event_stream
from ..adapters.llm import llm_status, polish_petition
from ..db import dumps_json, get_connection, loads_json, utc_now
from ..modules import (
    build_defender_safety_plan,
    build_evidence_codex,
    build_precedent_linker,
    build_procedural_engine,
)
from .audit import record_audit
from .intake import list_files
from .packaging import write_bundle
from .planning import load_plan


PETITION_TEMPLATE = """# {title}

**Jurisdiction:** {jurisdiction}
**Track:** {track_label} {citation}
**Drafted by:** Verda (lawyer signs and files)

## I. Parties
The petitioner(s) approach this Honourable Court under {citation_short} of the
Constitution of Kenya, 2010 alleging the violation of fundamental rights and
freedoms.

## II. Brief facts
{factual_summary}

## III. Issues for determination
{issues_block}

## IV. Constitutional and statutory framework
{framework_block}

## V. Chronology (extracted by Verda Evidence Codex)
{chronology_block}

## VI. Authorities (verified through kenyalaw-mcp)
{authorities_block}

## VII. Reliefs sought
1. A declaration that the detention of the petitioner(s) was unlawful and
   contrary to Articles 29, 49, and 51 of the Constitution.
2. An order for the immediate and unconditional release of the petitioner(s)
   into the custody of the court / advocate.
3. Compensation under Article 23 (3) (e) of the Constitution.
4. Any further and other relief this Honourable Court may deem fit.

## VIII. Advocate review checklist
- [ ] Confirm petitioner names and IDs
- [ ] Confirm respondent stations and named officers
- [ ] Verify every authority below by URL before signing
- [ ] Confirm jurisdiction-specific formatting (font, line spacing, marginals)
- [ ] Sign and file before {filing_deadline}
"""


def run_generation(case_id: int) -> dict[str, Any]:
    case_row = _load_case(case_id)
    if not case_row:
        raise ValueError(f"Case {case_id} not found")
    files = list_files(case_id)
    plan = load_plan(case_id)
    if not plan:
        raise ValueError("No toolkit plan saved; planner must run first")
    if not plan.get("approved"):
        raise ValueError("Toolkit plan has not been approved by a lawyer yet")

    started = time.monotonic()
    started_at = utc_now()
    mode = "openai" if llm_status()["configured"] else "deterministic"

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO generation_runs (case_id, generator_mode, started_at, status, summary_json)
            VALUES (?, ?, ?, 'running', '{}')
            """,
            (case_id, mode, started_at),
        )
        run_id = cursor.lastrowid

    record_audit(
        actor="orchestrator",
        action="run_generation_started",
        case_id=case_id,
        payload={"run_id": run_id, "mode": mode, "modules": [m["key"] for m in plan["modules"]]},
    )

    # Build artifacts.
    evidence_codex = build_evidence_codex(case_row, files)
    procedural_engine = build_procedural_engine(case_row, evidence_codex)
    precedent_linker = build_precedent_linker(case_row, evidence_codex)
    defender_safety = build_defender_safety_plan(case_row)
    petition_md = _draft_petition(case_row, evidence_codex, procedural_engine, precedent_linker)
    petition_md = polish_petition(case_row, petition_md, evidence_codex) or petition_md

    bundle = {
        "case_id": case_id,
        "case_summary": {
            "title": case_row["title"],
            "jurisdiction": case_row["jurisdiction"],
            "legal_track": case_row["legal_track"],
            "track_label": procedural_engine["track_label"],
            "citation": procedural_engine["citation"],
            "description": case_row["description"],
        },
        "generator_mode": mode,
        "plan": plan,
        "evidence_codex": evidence_codex,
        "procedural_engine": procedural_engine,
        "precedent_linker": precedent_linker,
        "defender_safety_build": defender_safety,
        "petition_draft": petition_md,
    }
    bundle_path = write_bundle(case_id, bundle)

    # Persist the agent event stream the UI replays.
    events = codex_event_stream(case_row, plan, evidence_codex, procedural_engine, precedent_linker, mode=mode)
    with get_connection() as conn:
        for sequence, ev in enumerate(events):
            conn.execute(
                """
                INSERT INTO generation_events (run_id, sequence, actor, kind, title, detail, file_path, delay_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    ev["actor"],
                    ev["kind"],
                    ev["title"],
                    ev.get("detail", ""),
                    ev.get("file_path"),
                    ev.get("delay_ms", 0),
                    utc_now(),
                ),
            )

    duration = time.monotonic() - started
    finished_at = utc_now()
    summary = {
        "events_extracted": evidence_codex["events_extracted"],
        "officers_named": evidence_codex["officers_named"],
        "ob_numbers_seen": evidence_codex["ob_numbers_seen"],
        "precedents_ranked": precedent_linker["result_count"],
        "deadlines": [s["deadline"] for s in procedural_engine["schedule"][:3]],
    }
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE generation_runs
            SET status = 'succeeded', finished_at = ?, duration_seconds = ?, bundle_path = ?, summary_json = ?
            WHERE id = ?
            """,
            (finished_at, round(duration, 3), bundle_path, dumps_json(summary), run_id),
        )
        conn.execute("UPDATE cases SET status = 'generated', updated_at = ? WHERE id = ?", (finished_at, case_id))

    record_audit(
        actor="orchestrator",
        action="run_generation_succeeded",
        case_id=case_id,
        payload={"run_id": run_id, "duration": round(duration, 3), **summary},
    )

    return {
        "run_id": run_id,
        "case_id": case_id,
        "mode": mode,
        "bundle_path": bundle_path,
        "duration_seconds": round(duration, 3),
        "summary": summary,
    }


def _load_case(case_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
    return item


def _draft_petition(
    case_row: dict[str, Any],
    evidence_codex: dict[str, Any],
    procedural_engine: dict[str, Any],
    precedent_linker: dict[str, Any],
) -> str:
    issues_block = "\n".join(
        f"{i + 1}. Whether the conduct of the respondents amounts to a violation of the petitioner's right "
        f"({item['name']}) under the Constitution of Kenya, 2010."
        for i, item in enumerate(evidence_codex.get("issue_heatmap", [])[:5])
    ) or "1. Whether the petitioner's constitutional rights were violated."

    framework_block = "\n".join(
        f"- Article {a} of the Constitution of Kenya, 2010"
        for a in (evidence_codex.get("articles_invoked") or ["29", "49", "51", "22", "23"])
    )

    chronology_block = "\n".join(
        f"- **{e.get('date') or 'undated'}**: {e.get('summary', '')[:180]} "
        f"_(source: {e.get('source_file')}:{e.get('line_number')})_"
        for e in (evidence_codex.get("timeline") or [])[:14]
    ) or "- _No structured chronology yet — re-run Codex once OCR completes._"

    authorities_block = "\n".join(
        f"- {r['title']} ({r['citation']}, {r['court']}) — relevance {r['relevance_score']:.2f}. URL: {r['url']}"
        for r in precedent_linker.get("results", [])[:5]
    ) or "- _No precedents matched yet; lawyer to expand kenyalaw-mcp queries._"

    deadline = "TBD"
    schedule = procedural_engine.get("schedule") or []
    if schedule:
        deadline = schedule[0]["deadline"]

    return PETITION_TEMPLATE.format(
        title=case_row["title"],
        jurisdiction=case_row["jurisdiction"].upper(),
        track_label=procedural_engine["track_label"],
        citation=procedural_engine.get("citation", ""),
        citation_short=(procedural_engine.get("citation") or "Articles 22 and 23").split(",")[0],
        factual_summary=case_row.get("description") or "Facts to be confirmed by lawyer.",
        issues_block=issues_block,
        framework_block=framework_block,
        chronology_block=chronology_block,
        authorities_block=authorities_block,
        filing_deadline=deadline,
    )


def list_runs(case_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM generation_runs WHERE case_id = ? ORDER BY id DESC", (case_id,)
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["summary"] = loads_json(item.pop("summary_json", "{}"))
        out.append(item)
    return out


def list_events(run_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM generation_events WHERE run_id = ? ORDER BY sequence ASC", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def latest_run(case_id: int) -> dict[str, Any] | None:
    runs = list_runs(case_id)
    return runs[0] if runs else None
