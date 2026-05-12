# Verda — security & threat model

Verda's users include defenders working in jurisdictions where seizure of
devices, compelled disclosure, and direct surveillance are real threats.
This document maps the canonical threat model from
`Verda_Technical_Architecture.pdf` §7 onto what is implemented in this MVP.

| Threat                       | Architecture mitigation                                                | MVP implementation                                                     |
| ---------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Device seizure               | Encrypted-at-rest case stores; Argon2id; panic-wipe                    | AES-256-GCM bundle encryption with scrypt KDF (N=2¹⁵). Panic-wipe declared in `defender_safety_build`; physical implementation is host-OS specific (Tails). |
| Compelled cloud disclosure   | Self-hosted mode; org-managed encryption keys                          | Self-hosted Docker manifest emitted alongside every bundle. No central server in default deployment. |
| LLM data leakage             | OpenAI no-training endpoint; structured summaries only                 | `adapters/llm.py` only sends Evidence Codex summary + petition draft. Raw evidence text never leaves the host. |
| Network surveillance         | Tor onion-service; sneakernet via USB                                  | USB manifest emitted. Tor wrapping is host-level; not implemented in code. |
| Insider risk                 | Per-case access control; immutable audit                               | Audit log on every MCP call, every Codex prompt, every export. |
| Generated code defects       | Codex-written tests + mandatory human review                           | 24 unit + e2e tests in `backend/tests/`. `SIGN BEFORE FILING` placeholder in every drafted motion. |
| Prompt injection via evidence | Evidence wrapped in untrusted-content markers                          | `AGENTS.md` declares evidence as untrusted content; LLM adapter passes structured summaries, not raw text. |

## Cryptography choices

`backend/wakili/services/encryption.py` implements AES-256-GCM with:

- KDF: `hashlib.scrypt(N=2**15, r=8, p=1, dklen=32, maxmem=64MiB)`
- 16-byte random salt per encryption
- 12-byte random nonce per encryption (NIST SP 800-38D)
- 16-byte authenticated GCM tag
- Constant-time tag comparison

The blob format is:

```
WAKILI1 (7B) || salt (16B) || nonce (12B) || ciphertext || tag (16B)
```

The implementation is pure Python (no C extension required) so it audits in
about 200 lines and runs in air-gapped environments. Production builds
should swap to the `cryptography` library's GCM backend for performance.

## What the MVP does not protect against

- Compromise of the host operating system. If the laptop running Verda is
  rooted, all evidence and generated artifacts are exposed. The USB-bootable
  manifest mitigates by booting an amnesic Tails-style OS.
- Coercion of the lawyer. No software can prevent a lawyer from being
  compelled to disclose; the architecture instead minimises the data
  exposed (federated self-hosting, encrypted-at-rest case stores).
- Side-channel attacks on the pure-Python AES implementation. Production
  builds should use a hardened library.

## Audit trail

Every call recorded to `audit_log` is:

- the actor (`kenyalaw-mcp`, `orchestrator`, `intake`, `packager`, `lawyer`,
  `llm-adapter`, …)
- the action (`run_generation_started`, `lookup_judgments`, `polish_petition_called`)
- the resource (case id, citation, export path)
- the structured payload (token counts, sizes, error messages)
- the timestamp

The lawyer reviews this trail in the **Audit** tab of each case before any
filing leaves the system.
