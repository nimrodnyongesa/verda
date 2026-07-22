# Verda — QA Testathon Guide

> Written for the Andela AI Testathon. Everything here has been verified on a
> clean bring-up; no step is aspirational.

Welcome. This guide gives you everything you need to review Verda from a QA
perspective: what it does, how to run it, what to test, and — just as
importantly — what is deliberately unfinished so you don't spend time filing
bugs against known stubs.

**Scope note:** this is a documentation-and-evaluation exercise. Participants
do not push code, open PRs, or modify the repository. Findings go into your
own QA report.

---

## 1. What Verda is

Verda turns a human rights defender's messy case file — police Occurrence
Book extracts, medical reports, WhatsApp exports, Swahili voice notes — into
a case-specific litigation toolkit that a lawyer can audit, edit, and file.

The MVP targets the **Kenyan Article 22 / 23 constitutional petition** track
and runs entirely on one laptop with no external services.

The pipeline, end to end:

| Stage | What happens |
| --- | --- |
| **Intake** | Drag a case folder in. Every readable file is ingested and classified. |
| **Plan** | A legal track is chosen, modules are proposed, deadlines are anchored to the earliest detected incident date, and risks are flagged. A **lawyer** must approve. |
| **Generation** | Four modules run: Evidence Codex (parses evidence into a timeline), Procedural Engine (jurisdiction state machine + drafted motions), Precedent Linker (ranked Kenya Law authorities), Defender Safety Build (offline deployment manifests). |
| **Outputs** | Timeline, drafted petition, precedent list, procedure view, audit log. |
| **Export** | Plain zip, or an AES-256-GCM encrypted bundle with a self-contained `decrypt.py`. |

Everything generated lands on disk under `runtime/generated/case_<id>/` as
real, readable files.

### The core design rule

**Lawyer in the loop.** Verda produces drafts, never filings. Every drafted
motion carries a `SIGN BEFORE FILING` marker, and permission gates stop a
paralegal from approving a plan or exporting an encrypted bundle. If you find
a path that lets an unqualified role produce something that looks
file-ready, **that is a high-severity bug** — it is the single most important
invariant in the product.

---

## 2. Running it

### Requirements

- Python 3.12
- Node 20+
- Docker (for Keycloak)
- ~600 MB disk for the Keycloak image on first pull

### One-shot bring-up

```bash
make install       # one-time: Python venv + npm install
make stack         # boots Keycloak + backend + frontend
make stack-wait    # blocks until all three are healthy
make smoke         # 8-stage end-to-end verification
```

Then open **http://localhost:3000** → **Sign in** → **Continue with Keycloak**.

Other useful targets:

```bash
make stack-logs    # tail -f backend + frontend logs
make stack-down    # stop everything cleanly
make test          # 67 backend tests
make sample-case   # copy the sample case folder to ./sample-case/
```

### Verifying your environment is good

`make smoke` walks a real PKCE Authorization Code flow against Keycloak,
exchanges the code, opens a session cookie, calls the backend through the
proxy, and creates a case stamped with the signed-in user. **If all 8 stages
are green, your environment is correct** and any failure you see afterwards is
a real finding, not a setup problem.

If `make smoke` fails, that is a setup issue — please raise it with us before
filing bugs.

### Ports

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend API | http://127.0.0.1:8765 |
| Backend API docs (Swagger) | http://127.0.0.1:8765/docs |
| Keycloak | http://localhost:8080 (`admin` / `admin`) |

---

## 3. Test accounts

Seeded automatically by the Keycloak realm import:

| Username | Password | Role | Can approve plans? | Can export encrypted? |
| --- | --- | --- | --- | --- |
| `advocate` | `advocate` | lawyer | ✅ | ✅ |
| `paralegal` | `paralegal` | paralegal | ❌ | ❌ |
| `nimrod` | `nimrod` | admin + lawyer | ✅ | ✅ |

The `paralegal` restrictions are **intentional**, not bugs. They are the
lawyer-in-the-loop boundary. Testing that they hold — including via direct
API calls that bypass the UI — is very much in scope.

---

## 4. Sample data

You do **not** need to supply a real case file, and please do not use one —
real defender case data is sensitive.

The repo ships a synthetic case folder (11 files, ~48 KB) at:

```
backend/tests/fixtures/sample_case/
```

Or run `make sample-case` to copy it to `./sample-case/` for easy
drag-and-drop.

It contains six police OB extracts from different Nairobi stations, a
WhatsApp family-group export, a Swahili/English voice-note transcript, a
medical report, case notes, and photo metadata — synthetic data modelled on a
2024 protest-arrest scenario. It is designed to exercise cross-file entity
resolution (the same detainees appear across multiple stations under
inconsistent spellings).

---

## 5. What to test

Suggested areas, roughly in priority order:

**Authentication & authorization (highest value)**
- Sign-in / sign-out / session expiry across all three accounts
- Role boundaries — especially whether `paralegal` restrictions hold when you
  call `/api/be/...` directly with a session cookie rather than using the UI
- Case ownership and membership: can one user reach another user's case?
  A non-member should get **404, not 403** (deliberate — it avoids leaking
  case existence)

**Intake**
- Folder and multi-file upload, drag-and-drop vs. browse
- Unreadable, empty, zero-byte, very large, and oddly-named files
- Non-Latin filenames and content (the sample data includes Swahili and Arabic
  is supported in the UI locales)

**Plan & generation**
- Plan approval gating
- The generation replay stream at various speeds (2× → 16×)
- Behaviour if you navigate away mid-generation, or run generation twice

**Outputs**
- Timeline: does every event trace back to a real source file and line?
- Petition: are all citations backed by a real Kenya Law URL?
- Precedents, procedure, audit log

**Export**
- Zip export
- Encrypted bundle: passphrase rules (≥ 8 chars), and whether the bundled
  `decrypt.py` actually round-trips
- Whether a wrong passphrase fails cleanly rather than producing garbage

**Cross-cutting**
- The five UI locales: English, Swahili, French, Portuguese, Arabic
  (Arabic is RTL — layout issues there are worth reporting)
- Responsive / mobile layout
- Accessibility: keyboard navigation, focus order, screen-reader labels,
  contrast
- Error states and empty states throughout

---

## 6. Known limitations — please don't file these

These are deliberate MVP scope decisions, already documented in the roadmap.
Reports against them aren't useful to us.

| Area | Status |
| --- | --- |
| **OCR** | Stubbed. PDFs and images are accepted and stored, but text is **not** actually extracted — you get a placeholder marked `ocr_required`. Real OCR is a planned subprocess call. |
| **Audio transcription** | Stubbed the same way (`transcription_required`). The Swahili voice-note **transcript** in the sample data is a pre-written `.txt` file, not live Whisper output. |
| **`africanlii` MCP server** | Deliberate stub with an empty corpus. It returns no results by design and only records the call for audit. `kenyalaw` and `case-knowledge` are real. |
| **LLM polish pass** | Off unless `OPENAI_API_KEY` is set. The default path is a deterministic generator. Please test the **deterministic** path — that is the shipped baseline. |
| **Database** | SQLite, with a Postgres-shaped schema. Postgres/pgvector is a planned swap, not a bug. |
| **Jurisdictions** | Kenya only. Uganda and Tanzania are roadmap. |
| **Codex cloud agent** | Not wired up. The local deterministic generator emits the same artifact shape and event stream. |
| **Performance at scale** | Untested above a few hundred files per case, and not a priority for this MVP. |

Also out of scope: the AGPL/trademark/governance files, the CI workflows, and
Dependabot's dependency-update PRs.

**Security testing:** please stay at the application level — role boundaries,
input validation, session handling, access control. Do **not** run automated
vulnerability scanners or attempt DoS against the stack. If you find something
genuinely sensitive, follow [`SECURITY.md`](../SECURITY.md) and report it
privately rather than in your public QA report.

---

## 7. Reporting findings

Useful bug reports include:

1. Account used (`advocate` / `paralegal` / `nimrod`)
2. Exact steps, starting from a fresh `make stack`
3. Expected vs. actual
4. Screenshot or the relevant lines from `make stack-logs`
5. Your severity call, and why

Severity guidance for this project specifically:

- **Critical** — a role boundary is breached, one user reaches another's
  case data, or an unsigned draft can be exported as if it were file-ready
- **High** — data loss, an output that misattributes evidence to the wrong
  source file, or a fabricated citation
- **Medium** — broken flows, incorrect UI state, bad error handling
- **Low** — cosmetic, copy, layout

The "fabricated citation" case deserves emphasis: Verda is not allowed to emit
a legal citation that did not come back from a verified MCP call. If you find
one that has no backing URL, that is a serious finding.

---

## 8. Questions

Open a GitHub Discussion on the repository, or reach the maintainer through
the contact in [`SECURITY.md`](../SECURITY.md) for anything sensitive.

Thanks for testing — the feedback genuinely helps a tool built for people who
need it.
