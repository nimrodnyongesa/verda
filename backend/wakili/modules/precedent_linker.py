"""Precedent Linker — per-case ranker over a Kenya Law / AfricanLII style corpus.

Each cited judgment is verified against the local kenyalaw-mcp corpus before being
included; per the architecture doc, citations Codex emits without provenance are
forbidden.

Ranking blends:
  * Article-citation overlap with the case (high signal — same constitutional axis)
  * Issue-keyword overlap with the case's issue heatmap
  * A binding-court boost (Supreme > Court of Appeal > High Court > Subordinate)
"""
from __future__ import annotations

import math
import re
from typing import Any

from ..mcp.kenyalaw import lookup_judgments

COURT_BOOST = {
    "Supreme Court": 0.30,
    "Court of Appeal": 0.20,
    "High Court": 0.10,
    "Magistrate's Court": 0.0,
}


def build_precedent_linker(
    case_row: dict[str, Any], evidence_codex: dict[str, Any]
) -> dict[str, Any]:
    case_articles = set(evidence_codex.get("articles_invoked") or [])
    issues = [item["name"] for item in evidence_codex.get("issue_heatmap", [])[:6]]
    issue_tokens = set()
    for issue in issues:
        issue_tokens.update(_tokens(issue))

    candidates = lookup_judgments(jurisdiction=case_row.get("jurisdiction", "ke"))
    scored: list[dict[str, Any]] = []
    for j in candidates:
        score, reasons = _score(j, case_articles, issue_tokens)
        if score <= 0:
            continue
        scored.append({
            **j,
            "relevance_score": round(score, 3),
            "match_reasons": reasons,
        })
    scored.sort(key=lambda c: c["relevance_score"], reverse=True)

    queries = _suggested_queries(case_row, issues)

    return {
        "jurisdiction": case_row.get("jurisdiction", "ke"),
        "case_articles": sorted(case_articles),
        "issues_used": issues,
        "results": scored[:10],
        "result_count": len(scored),
        "suggested_queries": queries,
        "verification_note": (
            "Each citation links to the kenyalaw-mcp record used. The lawyer must "
            "verify URL, holding, and binding force before relying on any cite in a filing."
        ),
    }


def _score(
    judgment: dict[str, Any], case_articles: set[str], issue_tokens: set[str]
) -> tuple[float, list[str]]:
    j_articles = set(judgment.get("articles_cited") or [])
    j_tokens = set()
    for issue in judgment.get("issues") or []:
        j_tokens.update(_tokens(issue))
    j_tokens.update(_tokens(judgment.get("summary", "")))

    article_overlap = len(case_articles & j_articles)
    issue_overlap = len(issue_tokens & j_tokens)
    base = 0.0
    reasons: list[str] = []
    if article_overlap:
        base += 0.45 * math.log1p(article_overlap) / math.log1p(3)
        reasons.append(f"shared articles: {sorted(case_articles & j_articles)}")
    if issue_overlap:
        base += 0.35 * math.log1p(issue_overlap) / math.log1p(6)
        reasons.append(f"issue overlap ({issue_overlap} tokens)")
    boost = COURT_BOOST.get(judgment.get("court", ""), 0.0)
    if boost > 0:
        base += boost
        reasons.append(f"binding court: {judgment.get('court')}")
    return min(base, 1.0), reasons


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())}


def _suggested_queries(case_row: dict[str, Any], issues: list[str]) -> list[str]:
    track = case_row.get("legal_track", "article_22_petition").replace("_", " ")
    base = [
        f"Kenya {track} unlawful detention",
        f"Kenya {track} freedom of assembly",
        f"Kenya conservatory orders police misconduct",
    ]
    base.extend(f"Kenya {issue} constitutional petition" for issue in issues[:3])
    seen: set[str] = set()
    out: list[str] = []
    for q in base:
        if q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out
