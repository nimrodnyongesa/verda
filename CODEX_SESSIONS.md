# Codex sessions — build journal

> The chronological story of how Verda was built by Codex agents
> operating against the doctrine in [`.codex/`](./.codex/README.md).
> One entry per substantive session. Verbatim status, not marketing.

Each session opens by reading `AGENTS.md`, the latest entries in
`.codex/plans/`, and the relevant `.codex/decisions/`. Each session closes
by updating those same folders. The code on disk is what the agent
emitted; the markdown next to it is why.

---

## 2026-04-26 — Shape session

- Scope: decide the unit of output. "Working software per case", not chat.
- Output: `.codex/decisions/001-codex-native-not-chat-native.md`.
- Code: empty repo, just `AGENTS.md` and the `.codex/` tree.

## 2026-04-29 — Architecture skeleton

- Scope: stand up the four-module shape (Evidence Codex, Procedural
  Engine, Precedent Linker, Defender Safety Build).
- Output: FastAPI surface stubbed, SQLite schema sketched, Next.js
  scaffolded. Reasoning captured in
  `.codex/thought_process/2026-04-29-shape-decisions.md`.
- Lesson: the schema went in PG-shaped from day one. Cheap now, cheap
  later when we swap to Postgres.

## 2026-05-01 — Evidence Codex generator

- Scope: deterministic parser + redaction pass against the synthetic
  sample case in `backend/tests/fixtures/sample_case/`.
- Output: `backend/wakili/modules/evidence_codex/`, 11 tests green.
- Failure mode: first cut leaked filenames into log lines. Caught by
  `test_evidence_codex.py::test_no_pii_in_logs`. Fixed in-session.

## 2026-05-02 — Procedural Engine + Precedent Linker

- Scope: state machine for KE Article 22/23 procedural rules; precedent
  fetcher that only emits cites with verified URLs.
- Output: `procedural_engine/`, `precedent_linker/`, MCP stub for
  `kenyalaw-mcp`. ADR not yet promoted; lived in chat.
- Lesson: forbid the generator from emitting any cite without an MCP
  receipt. Promoted to a hard rule in the planner prompt.

## 2026-05-03 — Defender Safety Build (first attempt)

- Scope: USB + Docker + encrypted bundle exports.
- Output: half-working. The Docker template self-collided on nested
  f-strings; `_layout` threw `NameError` on every request.
- Lesson: when you template Python with Python, double-double-brace your
  literals. Recorded in
  `.codex/thought_process/2026-05-05-real-exports.md`.

## 2026-05-04 — UI redesign session

- Scope: collapse the multi-route workspace into one. Reduce the surface
  the user has to learn.
- Output: `.codex/plans/2026-05-04-ui-redesign.md` (done),
  `.codex/decisions/006-single-route-workspace.md`.
- Reasoning: `.codex/thought_process/2026-05-04-ui-redesign.md`.

## 2026-05-05 — Keycloak + real exports + real corpus

- Triple session, three plans closed in one day:
  - `plans/2026-05-05-keycloak-auth.md` → done. ADRs 003, 004, 007.
  - `plans/2026-05-05-real-exports.md` → done. ADR 002.
  - `plans/2026-05-05-real-corpus.md` → done. ADR 005.
- Validation files (`auth-flow-end-to-end.md`, `exports-end-to-end.md`,
  `corpus-real.md`) all written same-day.

## 2026-05-07 — Audit log hardening

- Scope: every MCP call must hit the audit table; every drafted cite
  must carry its verification URL.
- Output: per-case audit tab populated; coverage gap closed.
- Reasoning: `.codex/thought_process/2026-05-07-audit-log-hardening.md`.

## 2026-05-08 — Smoke-test design

- Scope: a single command that proves the whole sign-in + API path. Not
  a unit test — a *deployment readiness* gate.
- Output: `scripts/smoke.sh`, eight checks, target `make smoke`.
  Promoted to merge gate.
- Decision: `.codex/decisions/008-smoke-test-as-readiness-gate.md`.

## 2026-05-10 — Demo rehearsal

- Scope: dry-run the demo end-to-end with the seeded `advocate` user.
  Time the steps. Identify the brittle bits.
- Output: `.codex/playbooks/demo-prep.md` updated; one timing fix to the
  generation-replay default speed (4× → 8×).
- Reasoning: `.codex/thought_process/2026-05-10-demo-rehearsal.md`.

## 2026-05-11 — Capstone submission plan

- Scope: line up the deliverables — video walkthrough, GitHub repo,
  portal submission — against the actual deadline.
- Output: `.codex/plans/2026-05-11-capstone-submission.md` (in flight).
- Decision: `.codex/decisions/009-no-telemetry-default-posture.md`
  promoted from informal convention to ADR so the submission packet has
  it on the record.

## 2026-05-12 — Walkthrough recording

- Scope: write the 5-minute transcript, rehearse, record.
- Output: video script under 5 minutes, hits all four pillars (Evidence
  Codex, Procedural Engine, Precedent Linker, Defender Safety Build) and
  the trust story (audit log, SIGN BEFORE FILING markers, no telemetry).
- Reasoning: `.codex/thought_process/2026-05-12-capstone-submission.md`.

---

## How to read this file

- Dates are absolute. No "last week", no "recently".
- Every session names the artifact it produced (file, plan, ADR) so you
  can `grep` from a session to its consequences.
- "Failure mode" / "Lesson" lines are deliberate. If a session went
  cleanly, that gets one line too.
- This file is append-only. Don't rewrite old entries — supersede them
  with a new dated entry instead.
