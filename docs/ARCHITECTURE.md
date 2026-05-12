# Verda — implementation notes

This is the developer reference for the MVP that ships with this repo. It
documents what is implemented in code today and where the implementation
diverges (deliberately, for local-first runnability) from the canonical
architecture in `Verda_Technical_Architecture.pdf`.

## Layers

### 1. Intake

`backend/wakili/services/intake.py` accepts uploaded files, computes content
hashes, runs evidence-type classification, and stores both the bytes and the
extracted text in SQLite.

Classification rules live in
`backend/wakili/modules/evidence_codex.py::classify_evidence_kind`. Categories
include `ob_extract`, `whatsapp_export`, `medical_report`, `case_notes`,
`audio`, `pdf`, `photo`, `csv`, `text`. The ruleset is deliberately small;
it triggers off well-known markers (OB number patterns, WhatsApp timestamp
prefix, medical / clinical keywords) and uses suffix matching as a fallback.

### 2. Knowledge

The MVP uses SQLite under `runtime/wakili.db`. Schema lives in
`backend/wakili/db.py::SCHEMA`. The schema is intentionally
Postgres-compatible — swapping to Postgres + pgvector is a one-shot rewrite
of `db.py`'s connection layer.

Whisper / Tesseract integration is stubbed; the rest of the pipeline accepts
the OCR/transcript output shape and works the moment those binaries are
wired in (`services/preprocessing.py::extract_text_from_bytes`).

### 3. Orchestration

`backend/wakili/services/orchestrator.py::run_generation` is the spine. It:

1. Loads the case + files + plan
2. Verifies the plan has been approved (rejects otherwise)
3. Records a `generation_runs` row with status `running`
4. Runs the four generators in sequence (Evidence Codex → Procedural Engine
   → Precedent Linker → Defender Safety Build)
5. Optionally polishes the petition via the OpenAI adapter (no-op without an
   API key)
6. Writes the bundle directory with reviewable Python modules
7. Persists the Codex agent event stream the UI replays
8. Marks the run `succeeded` and updates the case status to `generated`

In a full deployment, step 4 would dispatch to Codex cloud agents via
`backend/wakili/adapters/codex_replay.py`. The deterministic generator IS
the agent in the MVP; both paths produce the same artifact shape.

### 4. Generation

The four modules are in `backend/wakili/modules/`:

- `evidence_codex.py` — extracts a per-case timeline + entity index. The
  output is stable JSON with provenance pointers (file id + line number) on
  every event.
- `procedural_engine.py` — loads `procedural_rules.json` for the chosen
  track, computes a deadline schedule, and renders motion templates with
  case-specific values. Templates live in
  `backend/wakili/data/jurisdictions/ke/templates/`.
- `precedent_linker.py` — ranks `kenyalaw-mcp` results against the case's
  articles + issues with a documented scoring formula
  (article overlap × 0.45 + issue overlap × 0.35 + binding-court boost up
  to 0.30).
- `defender_safety.py` — declares deployment targets and packaging policy
  (telemetry off, encryption parameters, panic-wipe support).

### 5. Deployment

`backend/wakili/services/packaging.py` writes the bundle directory and
exposes export functions. `backend/wakili/services/encryption.py`
implements AES-256-GCM with a scrypt KDF and a `WAKILI1` magic header so a
defender can decrypt with the included Python utility even if Verda itself
is not installed on the receiving machine.

## MCP servers

`backend/wakili/mcp/` implements three MCP-style services:

- `kenyalaw-mcp` — structured access to a small Kenya Law judgment corpus
  (`backend/wakili/data/corpora/kenyalaw/judgments.json`). Each result
  carries a verifiable URL.
- `africanlii-mcp` — stub; logs every call to the audit table.
- `case-knowledge-mcp` — structured query over the active case's evidence.

Every call records to `audit_log`. `GET /api/audit?case_id=…` returns the
full per-case trail; `GET /api/audit` returns the global trail.

## Codex Skills

Skills live as Markdown contracts under
`backend/wakili/data/jurisdictions/ke/skills/`. Each `SKILL.md` declares the
hard rules a Codex run must obey (provenance pointers, no auto-signed
filings, no unverified citations). When the orchestrator dispatches to a
real Codex agent, these files sit alongside `AGENTS.md` in the scoped
workspace.

## Frontend

Next.js 16 App Router. Server Components by default; client components
(`"use client"`) only where interactivity is needed (upload zone,
generation replay player, plan-approval flow, export panel).

The root `next.config.ts` rewrites `/api/*` to the backend at
`http://127.0.0.1:8765`. In a hosted deployment, set `WAKILI_API_BASE` to
the backend URL.

## Tests

`backend/tests/` covers:

- `test_evidence_codex.py` — entity classification + provenance assertions
- `test_procedural_engine.py` — schedule monotonicity, motion rendering,
  rule-citation propagation
- `test_precedent_linker.py` — URL provenance, ranking direction
- `test_packaging.py` — bundle round-trip + zip export contents
- `test_encryption.py` — AES-256-GCM round-trip + tag rejection + truncation
- `test_e2e.py` — Finance Bill demo end-to-end + plan-approval gate
- `test_api.py` — FastAPI surface (health, demo seed, generation, exports
  including encrypted bundle decrypted back through the encryption module)

Run: `make test`.

## What's deliberately stubbed in the MVP

- **Whisper transcription** — the demo ships transcripts as plain text with
  `[Whisper-large-v3]` annotations. The adapter shape is final; replacing
  it is a one-file change.
- **Tesseract OCR** — same shape. PDFs and images are accepted and stored;
  their `extracted_text` field carries a `[Pending OCR]` annotation that
  the parser handles gracefully.
- **Real Codex cloud agents** — the deterministic generator emits the same
  bundle and the same agent event stream the cloud agent would emit.
- **Celery / Redis / MinIO / Postgres** — the schema is PG-shaped; the
  orchestrator is sync but the API surface is async-ready. Production
  deployment would swap these in without API changes.
- **Auth + WebAuthn** — the MVP runs on `localhost`. Auth.js + WebAuthn is
  the recommended addition for hosted deployments.

The architecture is designed so that none of these substitutions require
changes outside the relevant adapter / service file.
