# Verda — running a live demo

This walks through a complete demo of the local MVP using your own evidence
folder. The previous canned "Finance Bill" seed has been removed; the
intended flow is now drag-and-drop from a real case folder.

## Pre-flight (T-5)

```bash
make install     # one-time
make stack       # boots Keycloak + backend + frontend
```

Open `http://localhost:3000` in Chrome and sign in with one of the bundled
demo accounts:

| User         | Password    | Roles               |
| ------------ | ----------- | ------------------- |
| `advocate`   | `advocate`  | lawyer              |
| `paralegal`  | `paralegal` | paralegal           |
| `nimrod` | `nimrod`| admin + lawyer      |

`paralegal` cannot approve the plan or export an encrypted bundle by design
— that gate is the lawyer-in-the-loop boundary.

## 0:00 · Setup

Drag a case folder onto the upload zone (or click **Browse folder**). Verda
creates a case stamped with you as the owner, ingests every readable file,
classifies each one, and drafts a plan. You're routed straight to the case
workspace.

## 0:45 · Plan

Open the **Plan** tab. The page shows:

- The legal track (e.g. Article 22 Constitutional Petition)
- 4 modules to generate, each with rationale and ETA
- Deadline anchors derived from the earliest detected incident date
- Risks: chronology gaps, missing case numbers, etc.

Click **Approve plan**. Paralegal accounts will see the button disabled —
that's the IAM permission `plan:approve` doing its job.

## 1:10 · Generation

Click **Generate toolkit**. The Codex agent stream replays the work end-to-
end: Evidence Codex → Procedural Engine → kenyalaw lookups → petition draft
→ bundle assembled. Each event references a real file written to
`runtime/generated/case_<id>/`.

## 1:50 · Output #1 — Timeline

**Timeline** tab. Every extracted event is clickable: source file, line
number, officer references, and OB numbers in context.

## 2:15 · Output #2 — Drafted petition

**Petition** tab. Kenya Law authorities are linked from `kenyalaw.org`.

## 2:35 · Output #3 — Encrypted bundle

**Export** tab → **Encrypted bundle** target. Pick a passphrase (≥ 8
chars). The download is a zip wrapper containing a `.wakili` blob, a
self-contained `decrypt.py`, and a README. To prove decryption to the
audience:

```bash
.venv/bin/python -c "
from wakili.services.encryption import decrypt
import zipfile, io
blob = open('/path/to/wakili_case_<id>.wakili', 'rb').read()
zf = zipfile.ZipFile(io.BytesIO(decrypt(blob, 'YOUR-PASSPHRASE')))
print('Decrypted bundle contains:')
for n in zf.namelist(): print(' -', n)
"
```

## 2:55 · Land

The same case, viewed through `paralegal`, shows the same data but with
**Approve plan** and **Encrypted bundle** disabled — proof that the IAM
layer is enforcing role-aware permissions.

## Backup plan

| Failure                | Fallback                                                  |
| ---------------------- | --------------------------------------------------------- |
| Frontend won't load    | Drive the demo via the FastAPI Swagger UI at `/docs`.     |
| Backend won't start    | `make test` — the unit + e2e suite proves the pipeline.   |
| Encrypted export fails | The zip target works without a passphrase.                |

## After the demo

```bash
ls runtime/generated/case_<id>/
```

Real parser modules, JSON outputs, drafted motions, and a README the lawyer
can audit.
