# SKILL · procedural-engine

**Purpose**: Generate a per-case Python state machine that encodes the
procedural rules of the selected legal track (Article 22, Article 23, etc.)
and computes deadlines + the next required action.

## When to apply
Apply for every case. The procedural engine is the spine of the toolkit —
deadlines drive everything else.

## Inputs you may rely on
- `jurisdictions/ke/procedural_rules.json` — rule pack
- `jurisdictions/ke/templates/*.md` — boilerplate motions
- The Evidence Codex output (for the anchor / incident date)

## Outputs you must produce
- `state_machine.py` — readable Python state machine
- `procedural_engine.json` — schedule + next-action snapshot
- `drafted_motions/<filing>.md` — boilerplate motion(s) with placeholders preserved

## Hard rules
- Use the rule citation from `procedural_rules.json`; do not invent one.
- Compute deadlines as `incident_date + offset_days` where `offset_days` is
  defined by the rule pack. Never guess offsets.
- Respect the SIGN_BEFORE_FILING placeholders in motion templates.

## Forbidden
- Do not auto-sign or pre-fill the advocate signature block.
- Do not add filings that are not in the rule pack — adding a new filing is
  a content task, not a Codex task.
