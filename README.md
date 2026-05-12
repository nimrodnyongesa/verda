# Verda

> Codex-built litigation toolkits for human rights defenders.
> One case at a time. In code. In Africa.

Verda turns a defender's messy case file — PDFs, photos, Swahili audio,
WhatsApp exports — into a deployable, case-specific litigation toolkit. Each
toolkit is real software the lawyer can audit, modify, and ship: an Evidence
Codex parser, a Procedural Engine state machine for the relevant jurisdiction,
a Precedent Linker, and a Defender Safety Build (offline-deployable Docker /
USB).

This repository is the open-core MVP focused on the Kenyan Article 22 / 23
constitutional petition track. It runs locally on a single laptop with no
external services required.

## Architecture

| Layer         | Implementation                                                                |
| ------------- | ----------------------------------------------------------------------------- |
| Intake        | Next.js 16 (App Router) + Tailwind v4. Drag-and-drop, multi-modal upload.     |
| Knowledge     | SQLite (PG-shaped schema), local on-disk evidence store. OCR/Whisper stubbed. |
| Orchestration | FastAPI 0.118+ with audit log. In-process generation; Celery is one swap away.|
| Generation    | Per-jurisdiction `AGENTS.md` + Codex Skills. Deterministic baseline.          |
| Deployment    | Docker manifest, USB manifest, AES-256-GCM encrypted bundles (scrypt KDF).    |
| IAM           | Keycloak SSO + role/permission matrix + per-case ownership / membership.      |

```
verda/
├── backend/                          FastAPI + Python 3.12
│   ├── wakili/
│   │   ├── api/                      cases, plan, generation, outputs, exports, mcp, audit
│   │   ├── modules/                  evidence_codex, procedural_engine, precedent_linker, defender_safety
│   │   ├── services/                 intake, preprocessing, planning, orchestrator, packaging, encryption, audit
│   │   ├── adapters/                 llm (OpenAI optional), codex_replay (agent stream)
│   │   ├── mcp/                      kenyalaw, africanlii, case_knowledge
│   │   └── data/
│   │       ├── jurisdictions/ke/     AGENTS.md, procedural_rules.json, motion templates, Codex Skills
│   │       └── corpora/kenyalaw/     verifiable judgment URLs
│   └── tests/                        evidence, procedural, precedent, packaging, encryption, e2e, api
│       └── fixtures/sample_case/     synthetic case data used by the test suite
└── frontend/                         Next.js 16 + Tailwind v4
    ├── app/                          home, cases, case detail (overview, plan, generation, timeline, petition, precedents, procedure, audit, export)
    ├── components/                   upload-zone, generation-replay, timeline-view, petition-view, precedent-list, procedure-view, audit-log, export-panel
    └── lib/                          api client, types
```

## Running locally

You need Python 3.12, Node 20+, and Docker. The repo ships a Python venv
at `.venv/` with FastAPI and httpx already installed.

### One-shot bring-up (recommended)

```bash
make stack         # boots Keycloak + backend + frontend, all in one go
make stack-wait    # blocks until all three are healthy
make smoke         # walks the full sign-in + API flow end-to-end (8 checks)
make stack-logs    # tail -f /tmp/wakili-{backend,frontend}.log
make stack-down    # stops everything cleanly
```

The first `make stack` pulls Keycloak (~600 MB) and warms the npm cache;
subsequent runs are seconds. After `make stack && make stack-wait`, open
**http://localhost:3000** → click **Sign in** → **Continue with Keycloak**.

`make smoke` performs an actual PKCE Authorization Code flow against
Keycloak using the demo credentials, exchanges the code, opens a session
cookie, fetches `/api/be/cases`, creates a case stamped with the signed-in
user's `sub`, and confirms the `/auth/permissions` endpoint returns a
permission set. If `make smoke` is green, the entire path from browser →
Keycloak → frontend → proxy → Bearer → FastAPI → SQLite works.

### Demo / test credentials (seeded by the realm import)

| Username | Password | Role |
| --- | --- | --- |
| `advocate` | `advocate` | lawyer |
| `paralegal` | `paralegal` | paralegal |
| `nimrod` | `nimrod` | admin + lawyer |

These also drive `make smoke` (override with `WAKILI_DEMO_USER` /
`WAKILI_DEMO_PASSWORD` env vars).

### Manual bring-up (if you want to see each shell)

```bash
make keycloak               # boots Keycloak; waits for OIDC discovery
cp .env.example .env        # auth is ON by default in .env.example
source .env && make backend   # shell A
source .env && make frontend  # shell B
```

Then visit `http://localhost:3000`. Sign in with one of the demo creds
above and drop a case folder on the upload zone. Verda creates the case,
ingests every readable file, drafts a plan, and routes you to the
workspace. Approve the plan and click **Generate toolkit** — the Codex
agent stream replays at the speed of your choice (2× → 16×); the artifacts
on disk are real Python the lawyer can read.

## Testing

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests -v
```

39 tests cover the four generated modules, encryption round-trip + tag
rejection, packaging, the FastAPI surface, the IAM dependencies, and the
sample-case end-to-end flow.

## Optional OpenAI integration

```bash
export OPENAI_API_KEY="sk-…"
export WAKILI_OPENAI_MODEL="gpt-4o-mini"
```

When the key is set, the orchestrator polish-passes the petition through
OpenAI's no-training endpoint. Per the architecture's threat model, **raw
evidence is never sent** — only structured, provenance-tagged summaries (the
Evidence Codex output) cross the network. Without the key, the deterministic
baseline runs end-to-end and produces the same artifacts.

## Security

- Encrypted bundles use AES-256-GCM with a scrypt KDF (N=2¹⁵, r=8, p=1) and
  a constant-time tag check.
- The MCP servers (`kenyalaw-mcp`, `africanlii-mcp`, `case-knowledge-mcp`)
  log every call to the audit table, viewable per-case on the **Audit** tab.
- Codex is forbidden from emitting citations that did not come back from a
  verified MCP call. The verification URL is preserved alongside every cite.
- No telemetry by default. Anonymised stats are opt-in only and aggregated
  client-side first.
- Self-hosted Docker and USB-bootable build manifests are emitted alongside
  the bundle for partner orgs that cannot trust the cloud.

## Roadmap

The MVP covers Kenya Article 22 / 23. Adding a jurisdiction is a content task,
not a code task: drop a new `AGENTS.md`, a `procedural_rules.json`, and a
template pack into `backend/wakili/data/jurisdictions/<code>/`. The same
generators apply.

- East-Africa expansion: Uganda, Tanzania.
- Real OCR + Whisper integration (binaries are one subprocess call away).
- Postgres + pgvector swap-in (the schema is already PG-shaped).
- Real Codex cloud-agent integration; the deterministic generator already
  emits the same artifact shape and event stream.

## Lawyer in the loop

Verda produces drafts and tools. A licensed advocate signs and files. The
Law Society of Kenya rules of professional conduct are met because the human
lawyer is the responsible practitioner at every step. `SIGN BEFORE FILING`
markers in every drafted motion enforce that separation.

Built from Nairobi, not exported to it. 🇰🇪
