"""kenyalaw-mcp — structured access to Kenya Law judgments.

The corpus lives at data/corpora/kenyalaw/judgments.json. Each result returned
includes the URL the lawyer must verify before relying on the cite. This is the
documented mitigation for hallucinated citations: Codex can only emit citations
that came back from this server.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import CORPORA_DIR
from ..services.audit import record_audit


@lru_cache(maxsize=1)
def _load_corpus() -> list[dict[str, Any]]:
    path = CORPORA_DIR / "kenyalaw" / "judgments.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_judgments(jurisdiction: str = "ke", *, query: str | None = None) -> list[dict[str, Any]]:
    """Return judgments matching the given filters."""
    corpus = _load_corpus()
    record_audit(
        actor="kenyalaw-mcp",
        action="lookup_judgments",
        resource=f"jurisdiction={jurisdiction};query={query or '*'}",
        payload={"jurisdiction": jurisdiction, "query": query, "corpus_size": len(corpus)},
    )
    if jurisdiction and jurisdiction != "ke":
        return []
    if not query:
        return list(corpus)
    needle = query.lower()
    return [
        j
        for j in corpus
        if needle in j.get("title", "").lower()
        or needle in j.get("summary", "").lower()
        or needle in j.get("body_text", "").lower()
    ]


def get_judgment(citation: str) -> dict[str, Any] | None:
    record_audit(
        actor="kenyalaw-mcp",
        action="get_judgment",
        resource=citation,
        payload={"citation": citation},
    )
    for j in _load_corpus():
        if j.get("citation") == citation:
            return j
    return None
