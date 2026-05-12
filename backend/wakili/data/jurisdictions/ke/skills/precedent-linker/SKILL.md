# SKILL · precedent-linker

**Purpose**: Generate a per-case scraper + ranker that finds Kenya Law
judgments matching the argument structure of the case.

## When to apply
Apply for every case. The petition's authority section depends on this skill.

## Inputs you may rely on
- `kenyalaw-mcp.lookup_judgments(query=...)` — Kenya Law search
- `africanlii-mcp.lookup_judgments(query=...)` — AfricanLII search
- The Evidence Codex's `articles_invoked` and `issue_heatmap`

## Outputs you must produce
- `precedent_scraper.py` — readable Python; documents the scoring formula
- `precedent_linker.json` — ranked results with relevance scores

## Hard rules
- Every cited judgment must have a working URL returned by `kenyalaw-mcp` or
  `africanlii-mcp`. Codex must record the URL alongside the citation.
- Ranking must combine: article overlap, issue-keyword overlap, and a
  binding-court boost (Supreme > Court of Appeal > High Court).
- The lawyer must be able to read the scoring rules in `precedent_scraper.py`.

## Forbidden
- **Never** emit a citation that did not come back from a verified MCP call.
- Do not silently drop low-score results — list everything; the lawyer
  decides what to plead.
