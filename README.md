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
wakili/
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
