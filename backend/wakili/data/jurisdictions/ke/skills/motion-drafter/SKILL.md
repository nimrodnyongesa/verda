# SKILL · motion-drafter

**Purpose**: Render the lawyer-approved motion templates with the case's
specific facts, parties, chronology, officer list, and verified authorities.

## When to apply
Apply when the procedural engine has produced a schedule and the precedent
linker has produced verified authorities.

## Inputs you may rely on
- `templates/notice_of_motion.md`, `supporting_affidavit.md`,
  `list_of_authorities.md`, `article_22_petition.md`
- Evidence Codex output (for chronology, officers, stations)
- Procedural Engine output (for deadlines and filings)
- Precedent Linker output (for the authorities block)

## Outputs you must produce
- `drafted_motions/notice_of_motion.md`
- `drafted_motions/supporting_affidavit.md`
- `drafted_motions/list_of_authorities.md`
- `petition_draft.md` — the substantive petition

## Hard rules
- Preserve `[SIGN BEFORE FILING …]` markers; never auto-sign.
- Preserve `[…]` placeholder brackets where the lawyer must complete a field.
- Use British English and the Constitution's spelling conventions.
- Where a value is unavailable, use `[VALUE PENDING]` rather than guessing.
