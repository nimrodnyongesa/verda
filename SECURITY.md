# Security Policy

## Supported versions

Verda is pre-1.0 and currently ships a single supported branch
(`main`). Security fixes land on `main` and are tagged. There is no
maintained "old" branch.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| < `main`| :x:                |

## Reporting a vulnerability

**Please do not open a public GitHub issue.** Verda is used by human
rights defenders working under surveillance pressure; a public report
puts them at risk before a fix can land.

Two channels — pick whichever you prefer:

1. **GitHub Private Vulnerability Reporting**
   <https://github.com/nyongesa637/verda/security/advisories/new>
   This is the preferred path — it's encrypted in transit, audit-logged,
   and gets a CVE automatically.

2. **Email (PGP-encrypted)**
   `security@verda.invalid` (replace `.invalid` with the actual TLD
   listed at <https://github.com/nyongesa637/verda#security-contact>).
   Encrypt with the PGP key fingerprint published in the same place.

Whichever channel you pick, include:

- A description of the issue and its impact.
- The exact version / commit SHA of Verda you tested against.
- Reproduction steps or a proof of concept (a private gist is fine).
- Your name / handle for the credit line, OR a clear request for
  anonymous reporting — we honour both.

## Our commitments

- **Acknowledgement** within 72 hours.
- **First-pass triage** within 7 days, with a severity rating
  (CVSS 3.1).
- **Coordinated disclosure**: we will publish a GitHub Security
  Advisory and a tagged release after the fix ships. We will not
  publish your name or any identifying details without your explicit
  consent.

## Scope

In scope:

- Anything in this repository's `main` branch.
- Cryptographic surface (AES-256-GCM bundle wrapper, scrypt KDF,
  `WAKILI1` magic header, the stdlib `decrypt.py` shipped inside
  encrypted bundles).
- OIDC token verification (JWKS rotation, `kid` matching, algorithm
  pinning).
- The MCP servers (`kenyalaw-mcp`, `africanlii-mcp`, `case-knowledge-mcp`)
  and the append-only audit log.
- The `/api/be/[...path]` proxy in the frontend.

Out of scope:

- Issues that require a malicious local user with write access to the
  defender's machine.
- Denial of service against the demo Keycloak realm or local SQLite
  database — Verda is single-tenant and self-hosted.
- Social-engineering of the lawyer-in-the-loop step (a human must sign
  every motion before filing).
- Findings in dependencies that have not been disclosed upstream — please
  report those upstream first.

## Hall of thanks

Coordinated-disclosure reporters who consent to credit will be listed
at the bottom of each release's GitHub Security Advisory and in
`docs/SECURITY.md`.

## A note on threat model

Verda is operated by individual lawyers on their own laptops, often in
parts of the world where the state may itself be the adversary. We
take that seriously:

- Telemetry is **off by default**. No phone-home.
- The cryptography is meant to survive an attacker with the encrypted
  bundle but not the passphrase.
- Bundled `decrypt.py` is pure stdlib so a defender can recover their
  data without Verda installed.
- The MCP audit log is append-only — there is no API to delete rows.
- `[SIGN BEFORE FILING]` markers in every drafted motion enforce the
  separation between machine and human accountability.

If your finding touches any of these guarantees, please flag it
explicitly when you report.
