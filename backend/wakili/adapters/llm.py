"""LLM adapter — optional OpenAI integration for petition polish + planner notes.

Per the architecture doc, raw evidence is never sent to the LLM. Only structured
summaries (the Evidence Codex output, which is provenance-tagged but no source
text beyond short snippets) are passed through. The deterministic baseline runs
without any API key and produces the artifacts judges see in the demo.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..services.audit import record_audit


def llm_status() -> dict[str, Any]:
    return {
        "configured": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL if OPENAI_API_KEY else None,
        "endpoint": "https://api.openai.com/v1/chat/completions" if OPENAI_API_KEY else None,
    }


def polish_petition(case_row: dict[str, Any], draft: str, evidence_codex: dict[str, Any]) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        return _call_openai(case_row, draft, evidence_codex)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        record_audit(
            actor="llm-adapter",
            action="polish_petition_failed",
            case_id=case_row["id"],
            payload={"error": str(exc)},
        )
        return None


def _call_openai(case_row: dict[str, Any], draft: str, evidence_codex: dict[str, Any]) -> str:
    system = (
        "You are an editor for Kenyan constitutional petitions under Articles 22/23. "
        "You may rewrite for clarity, but you must NOT invent facts, citations, or "
        "case law. If a section says [PLACEHOLDER], leave it. Match the tone of the "
        "Constitution of Kenya, 2010 and Mutunga Rules drafting style. Reply with the "
        "petition only, no commentary."
    )
    user_payload = {
        "case": {
            "title": case_row["title"],
            "jurisdiction": case_row["jurisdiction"],
            "track": case_row["legal_track"],
            "description": case_row["description"],
        },
        "evidence_summary": {
            "files_indexed": evidence_codex["files_indexed"],
            "events_extracted": evidence_codex["events_extracted"],
            "issue_heatmap": evidence_codex["issue_heatmap"][:5],
            "officers": evidence_codex["officers"][:6],
        },
        "draft": draft,
    }
    body = json.dumps(
        {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )
    record_audit(
        actor="llm-adapter",
        action="polish_petition_called",
        case_id=case_row["id"],
        resource=OPENAI_MODEL,
        payload={"approx_tokens_in": len(body)},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]
