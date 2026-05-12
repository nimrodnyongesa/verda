# SKILL · evidence-codex

**Purpose**: Generate a per-case Python parser that extracts a queryable
timeline + entity index from the case's evidence inventory.

## When to apply
Apply this skill when the planner identifies any text-bearing evidence in the
case folder (text, markdown, csv, OCR'd PDF, transcribed audio, WhatsApp
exports). Do not apply when the entire folder is non-text (e.g. only photos
without OCR).

## Inputs you may rely on
- `case-knowledge-mcp.list_evidence(case_id)` — file inventory
- `case-knowledge-mcp.get_evidence_text(case_id, file_id)` — preprocessed text
- `jurisdictions/ke/AGENTS.md` — drafting + naming conventions

## Outputs you must produce
- `evidence_parser.py` — readable Python, importable by the lawyer
- `evidence_codex.json` — extracted timeline with provenance pointers
- A unit test asserting that every timeline event carries a `source_file_id`
  and `line_number` provenance pointer

## Hard rules
- Every extracted event must carry a provenance pointer back to the source
  file and line.
- Date normalisation must produce ISO-8601 (`YYYY-MM-DD`).
- The parser must be deterministic for a given input; no LLM calls inside
  the parser hot path.
- Officer names must be paired with rank tokens (PC, Cpl, IP, OCS, …).

## Forbidden
- Do not hallucinate dates, officer names, or OB numbers that did not appear
  literally in the source text.
- Do not call out to the open web during parsing.
