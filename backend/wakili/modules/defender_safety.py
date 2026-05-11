"""Defender Safety Build — declares deployment targets and packaging policy.

The actual zip / encrypted bundle / docker manifest writing happens in
services/packaging.py and services/encryption.py; this module produces the plan
the lawyer reviews before the build is emitted.
"""
from __future__ import annotations

from typing import Any


SUPPORTED_TARGETS = [
    {
        "key": "hosted",
        "name": "Hosted instance",
        "description": "Default. Runs on the Verda-operated server with org-managed encryption keys.",
        "outbound_calls": "kenyalaw-mcp, OpenAI Codex (no-training endpoint), audit log only",
        "best_for": "Low-risk clinical work; orgs that prefer a managed deployment.",
    },
    {
        "key": "docker",
        "name": "Self-hosted Docker image",
        "description": "Single docker compose stack runs on the org's own infra.",
        "outbound_calls": "Only those the lawyer explicitly enables.",
        "best_for": "Strategic-litigation NGOs handling sensitive evidence.",
    },
    {
        "key": "usb",
        "name": "USB-bootable image",
        "description": "Tails-style live OS preloaded with the per-case toolkit and evidence bundle.",
        "outbound_calls": "None.",
        "best_for": "High-risk fact-finding trips, defenders working under surveillance.",
    },
    {
        "key": "encrypted",
        "name": "Encrypted bundle",
        "description": "Passphrase-protected archive (AES-256-GCM, scrypt KDF). Decryptable only on authorised devices.",
        "outbound_calls": "None.",
        "best_for": "Sneakernet / device handoff between defender teams.",
    },
]


def build_defender_safety_plan(case_row: dict[str, Any]) -> dict[str, Any]:
    _ = case_row  # reserved for org-policy lookups in future jurisdictions
    return {
        "telemetry_default": "off",
        "encryption_at_rest": {
            "algorithm": "AES-256-GCM",
            "kdf": "scrypt(N=2**15, r=8, p=1)",
            "key_source": "passphrase per export",
        },
        "panic_wipe_supported": True,
        "tor_onion_optional": True,
        "supported_targets": SUPPORTED_TARGETS,
        "default_target": "hosted",
        "advisories": [
            "Self-hosted mode never phones home. Anonymised stats are opt-in only.",
            "Encrypted bundles ship without metadata that identifies the case team.",
            "Voice-note transcripts are retained only as long as the case is open.",
        ],
        "bundle_contents": [
            "case_summary.json",
            "evidence_codex/timeline.json",
            "evidence_codex/parser_module.py",
            "procedural_engine/state_machine.py",
            "procedural_engine/schedule.json",
            "procedural_engine/drafted_motions/",
            "precedent_linker/results.json",
            "precedent_linker/scraper_module.py",
            "petition_draft.md",
            "audit_log.json",
            "AGENTS.md",
            "README.md",
        ],
    }
