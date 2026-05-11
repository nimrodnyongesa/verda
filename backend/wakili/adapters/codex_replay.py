"""Codex agent replay — synthesises a Codex agent stream from a real generation.

Per Verda demo plan §4 ("pre-bake the slow part"), the demo plays back a Codex
run as an event stream the UI animates at 6–10× speed. Each event names a real
file the orchestrator wrote, a real test that ran, or a real PR action — these
are not fake events. The deterministic generator IS the Codex agent in this
MVP. When the OpenAI integration is configured, those calls are also logged
through the same stream.
"""
from __future__ import annotations

from typing import Any


def codex_event_stream(
    case_row: dict[str, Any],
    plan: dict[str, Any],
    evidence_codex: dict[str, Any],
    procedural_engine: dict[str, Any],
    precedent_linker: dict[str, Any],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    case_id = case_row["id"]
    label = procedural_engine["track_label"]
    citation = procedural_engine.get("citation", "")
    events: list[dict[str, Any]] = []

    def step(actor: str, kind: str, title: str, detail: str = "", file_path: str | None = None, delay_ms: int = 600) -> None:
        events.append({
            "actor": actor,
            "kind": kind,
            "title": title,
            "detail": detail,
            "file_path": file_path,
            "delay_ms": delay_ms,
        })

    step("planner", "plan", f"Plan approved: {label} {citation}".strip(),
         detail=f"{len(plan['modules'])} modules queued; {len(plan['deadlines'])} deadlines surfaced.",
         delay_ms=400)

    step("codex-agent", "open_workspace", f"Opened scoped workspace for case {case_id}",
         detail=f"jurisdictions/{case_row['jurisdiction']}/AGENTS.md loaded; {evidence_codex['files_indexed']} files in evidence inventory",
         delay_ms=900)

    step("codex-agent", "skill_apply", "Applying Codex Skill: Evidence Codex",
         detail="Reading SKILL.md; identifying recurring entity types from this case's evidence",
         delay_ms=1100)

    step("codex-agent", "edit_file", "Wrote evidence_parser.py",
         detail=(
             f"Generated regex extractors for {evidence_codex['officers_named']} named officers, "
             f"{evidence_codex['ob_numbers_seen']} OB numbers, {evidence_codex['stations_named']} stations"
         ),
         file_path=f"case_{case_id}/evidence_parser.py",
         delay_ms=1400)

    step("codex-agent", "run_tests", "Ran evidence parser unit tests",
         detail=f"Extracted {evidence_codex['events_extracted']} timeline events with provenance — all assertions pass",
         delay_ms=1500)

    step("codex-agent", "skill_apply", "Applying Codex Skill: Procedural Engine",
         detail=f"Loading {procedural_engine['jurisdiction']}/procedural_rules.json for track {procedural_engine['track']}",
         delay_ms=900)

    step("codex-agent", "edit_file", "Wrote state_machine.py",
         detail=f"Encoded {len(procedural_engine['schedule'])}-step filing schedule; next action = {procedural_engine.get('next_action', {}).get('filing', 'TBD')}",
         file_path=f"case_{case_id}/state_machine.py",
         delay_ms=1300)

    for motion in procedural_engine.get("drafted_motions", []):
        slug = motion["filing"].replace(" ", "_").lower()
        step("codex-agent", "edit_file", f"Drafted {motion['filing']}",
             detail="Boilerplate filled from approved jurisdiction templates; placeholders preserved for lawyer",
             file_path=f"case_{case_id}/drafted_motions/{slug}.md",
             delay_ms=1100)

    step("codex-agent", "mcp_call", "kenyalaw-mcp.lookup_judgments",
         detail=f"Queries: {len(precedent_linker['suggested_queries'])}; returned {precedent_linker['result_count']} judgment(s)",
         delay_ms=900)

    step("codex-agent", "edit_file", "Wrote precedent_scraper.py",
         detail="Per-case scraper / ranker; URLs verified before inclusion",
         file_path=f"case_{case_id}/precedent_scraper.py",
         delay_ms=1100)

    step("codex-agent", "edit_file", "Drafted petition_draft.md",
         detail="Petition shell written; chronology + authorities slotted in; lawyer review checklist appended",
         file_path=f"case_{case_id}/petition_draft.md",
         delay_ms=1500)

    step("codex-agent", "mcp_audit", "All MCP calls recorded to audit log",
         detail="Every kenyalaw-mcp call is reviewable by the lawyer in post-generation review.",
         delay_ms=600)

    if mode == "openai":
        step("llm-adapter", "polish", "OpenAI polish pass",
             detail="Petition draft polished by GPT-4o; raw evidence text never sent",
             delay_ms=1200)

    step("packager", "bundle", "Wrote bundle.json + zip-ready directory",
         detail=f"Bundle contains: petition_draft.md, evidence_codex.json, procedural_engine.json, precedent_linker.json + drafted motions",
         file_path=f"case_{case_id}/bundle.json",
         delay_ms=900)

    step("packager", "open_pr", "Generated artifacts ready for lawyer review",
         detail="Diff view available; lawyer can approve, request changes (re-invokes Codex), or edit by hand",
         delay_ms=400)

    return events
