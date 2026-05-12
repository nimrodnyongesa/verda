"""Zip export — full bundle directory as a flat zip."""
from __future__ import annotations

import zipfile
from pathlib import Path

from ...config import EXPORTS_DIR, GENERATED_DIR, ensure_directories
from ..audit import record_audit


def export(case_id: int) -> Path:
    ensure_directories()
    src = GENERATED_DIR / f"case_{case_id}"
    if not src.exists():
        raise FileNotFoundError(f"No generated artifacts for case {case_id}")
    out_path = EXPORTS_DIR / f"wakili_case_{case_id}.zip"
    with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(src).as_posix())
    record_audit(
        actor="exporter",
        action="export_zip",
        case_id=case_id,
        resource=str(out_path),
        payload={"size_bytes": out_path.stat().st_size},
    )
    return out_path
