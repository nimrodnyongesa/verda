"""Packaging — write the per-case bundle directory.

Bundle export targets (zip, encrypted, docker, usb) live in
``services/exporters/``. This module is now solely responsible for laying
out the canonical bundle directory at ``runtime/generated/case_<id>/``
and producing the in-memory zip blob the encrypted exporter wraps.
"""
from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import Any

from ..config import GENERATED_DIR, ensure_directories
from ..db import dumps_json
from .audit import record_audit


def write_bundle(case_id: int, bundle: dict[str, Any]) -> str:
    ensure_directories()
    out_dir = GENERATED_DIR / f"case_{case_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_json_path = out_dir / "bundle.json"
    bundle_json_path.write_text(dumps_json(bundle), encoding="utf-8")

    (out_dir / "petition_draft.md").write_text(bundle["petition_draft"], encoding="utf-8")
    (out_dir / "evidence_codex.json").write_text(dumps_json(bundle["evidence_codex"]), encoding="utf-8")
    (out_dir / "procedural_engine.json").write_text(dumps_json(bundle["procedural_engine"]), encoding="utf-8")
    (out_dir / "precedent_linker.json").write_text(dumps_json(bundle["precedent_linker"]), encoding="utf-8")
    (out_dir / "defender_safety_build.json").write_text(dumps_json(bundle["defender_safety_build"]), encoding="utf-8")

    motions_dir = out_dir / "drafted_motions"
    motions_dir.mkdir(exist_ok=True)
    for motion in bundle["procedural_engine"].get("drafted_motions", []):
        slug = motion["filing"].replace(" ", "_").replace("/", "_").lower()
        (motions_dir / f"{slug}.md").write_text(motion["content"], encoding="utf-8")

    (out_dir / "evidence_parser.py").write_text(
        _render_parser_module(bundle["evidence_codex"]), encoding="utf-8"
    )
    (out_dir / "state_machine.py").write_text(
        _render_state_machine(bundle["procedural_engine"]), encoding="utf-8"
    )
    (out_dir / "precedent_scraper.py").write_text(
        _render_precedent_scraper(bundle["precedent_linker"]), encoding="utf-8"
    )
    (out_dir / "README.md").write_text(_render_bundle_readme(bundle), encoding="utf-8")

    record_audit(
        actor="packager",
        action="write_bundle",
        case_id=case_id,
        resource=str(bundle_json_path),
        payload={"bundle_size_bytes": bundle_json_path.stat().st_size},
    )
    return str(bundle_json_path)


def collect_bundle_bytes(case_id: int) -> bytes:
    """Return a deflated zip blob of the full bundle directory.

    Used by the encrypted exporter as the plaintext payload before
    AES-256-GCM encryption.
    """
    src = GENERATED_DIR / f"case_{case_id}"
    if not src.exists():
        raise FileNotFoundError(f"No generated artifacts for case {case_id}")
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(src).as_posix())
    return buf.getvalue()


def _render_parser_module(evidence_codex: dict[str, Any]) -> str:
    return f'''"""Generated Evidence Codex parser — Verda case-specific module.

Generated for case_id={evidence_codex['case_id']}. Reviewable, editable Python.
The parser was generated against this case's evidence inventory; it is not a
generic NER pipeline. Read it carefully before relying on it.
"""
from __future__ import annotations

import json
from pathlib import Path

PROVENANCE = {{
    "case_id": {evidence_codex['case_id']},
    "files_indexed": {evidence_codex['files_indexed']},
    "events_extracted": {evidence_codex['events_extracted']},
    "ob_numbers_seen": {evidence_codex['ob_numbers_seen']},
    "officers_named": {evidence_codex['officers_named']},
}}


def load_timeline() -> list[dict]:
    """Return the parsed timeline as a list of events with provenance."""
    here = Path(__file__).resolve().parent
    return json.loads((here / "evidence_codex.json").read_text(encoding="utf-8"))["timeline"]


if __name__ == "__main__":
    timeline = load_timeline()
    for ev in timeline:
        date = ev.get("date") or "undated"
        print(f"{{date}}\\t{{ev.get('source_file')}}:{{ev.get('line_number')}}\\t{{ev.get('summary', '')[:120]}}")
'''


def _render_state_machine(procedural_engine: dict[str, Any]) -> str:
    schedule = procedural_engine.get("schedule", [])
    items = ",\n    ".join(
        f'{{"filing": {json.dumps(s["filing"])}, "deadline": {json.dumps(s["deadline"])}, "status": {json.dumps(s["status"])}, "rule": {json.dumps(s.get("rule", ""))}}}'
        for s in schedule
    )
    return f'''"""Generated Procedural Engine — Verda case-specific state machine.

Track: {procedural_engine['track_label']}
Citation: {procedural_engine.get('citation', '')}
"""
from __future__ import annotations

from datetime import date, datetime

SCHEDULE = [
    {items}
]


def next_action(today: date | None = None) -> dict | None:
    today = today or date.today()
    for entry in SCHEDULE:
        deadline = datetime.strptime(entry["deadline"], "%Y-%m-%d").date()
        if (deadline - today).days >= 0:
            entry = dict(entry)
            entry["days_remaining"] = (deadline - today).days
            return entry
    return None


if __name__ == "__main__":
    print(next_action())
'''


def _render_precedent_scraper(precedent_linker: dict[str, Any]) -> str:
    queries = json.dumps(precedent_linker.get("suggested_queries", []), ensure_ascii=False)
    return f'''"""Generated Precedent Linker — Verda case-specific scraper / ranker.

This is the per-case scraper that runs against kenyalaw-mcp. Each cited URL
must be fetched and verified before any judgment is relied on in a draft
motion. The queries below were derived from this case's issue heatmap.
"""
from __future__ import annotations

QUERIES = {queries}


def fetch_judgments(client) -> list[dict]:
    """Call kenyalaw-mcp via the supplied client and rank results."""
    results: list[dict] = []
    for q in QUERIES:
        results.extend(client.lookup_judgments(query=q))
    return results
'''


def _render_bundle_readme(bundle: dict[str, Any]) -> str:
    case = bundle["case_summary"]
    return f"""# Verda Toolkit · Case {bundle['case_id']}

## {case['title']}

- **Jurisdiction:** {case['jurisdiction']}
- **Track:** {case['track_label']} {case['citation']}
- **Generator mode:** `{bundle['generator_mode']}`

## Contents

- `petition_draft.md` — drafted petition; lawyer signs and files
- `evidence_codex.json` — extracted timeline + entities
- `evidence_parser.py` — generated, reviewable parser module
- `procedural_engine.json` — schedule + drafted motions
- `state_machine.py` — generated state machine
- `precedent_linker.json` — ranked Kenya Law precedents (verified URLs)
- `precedent_scraper.py` — per-case scraper / ranker
- `defender_safety_build.json` — deployment policy
- `drafted_motions/` — one file per filing (notice of motion, supporting affidavit, list of authorities)
- `bundle.json` — full machine-readable bundle

## Lawyer review checklist

1. Verify every authority URL in `precedent_linker.json` before relying on a cite.
2. Confirm petitioner and respondent identifiers in each draft motion.
3. Review the `state_machine.py` schedule — the next required filing is at the top.
4. Replace any `[…]` placeholders in `petition_draft.md` before signing.

## Telemetry

`{bundle['defender_safety_build']['telemetry_default']}` by default. Anonymised stats opt-in only.
"""
