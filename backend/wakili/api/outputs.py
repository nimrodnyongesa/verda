from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response

from ..auth.access import CaseAccess
from ..auth.dependencies import User, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import Permission
from ..config import GENERATED_DIR
from ..services.document_exporter import render_docx, render_pdf

router = APIRouter()


_DOC_FORMATS = {
    "md": ("text/markdown; charset=utf-8", ".md"),
    "pdf": ("application/pdf", ".pdf"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
}


def _render_document(content: str, fmt: str, *, base_filename: str) -> Response:
    """Convert resolved markdown into the requested format.

    The Markdown source already comes from the procedural engine with
    every placeholder filled, but the document_exporter runs a second
    pass so a forgotten ``{{token}}`` never reaches the advocate's
    downloaded file. Any exception from the underlying renderer is
    converted into a 500 with a parseable JSON detail; the PDF renderer
    itself has a last-ditch fallback that emits a small valid PDF
    carrying the error, so a *corrupt* download is unreachable from this
    endpoint — the only failure mode is HTTP 500 with explanatory JSON.
    """
    if fmt not in _DOC_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")
    if not content:
        raise HTTPException(
            status_code=404,
            detail="Document is empty — generation may not have completed yet.",
        )
    mime, ext = _DOC_FORMATS[fmt]
    filename = f"{base_filename}{ext}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    try:
        if fmt == "md":
            body = content.encode("utf-8")
        elif fmt == "docx":
            body = render_docx(content)
        else:
            body = render_pdf(content)
    except Exception as exc:  # noqa: BLE001 — surface any rendering bug
        raise HTTPException(
            status_code=500,
            detail=f"{fmt.upper()} rendering failed: {type(exc).__name__}: {exc}",
        ) from exc

    if not body:
        raise HTTPException(
            status_code=500,
            detail=f"{fmt.upper()} renderer produced an empty document.",
        )
    headers["Content-Length"] = str(len(body))
    return Response(content=body, media_type=mime, headers=headers)


def _bundle_path(case_id: int):
    return GENERATED_DIR / f"case_{case_id}" / "bundle.json"


def _read_perm() -> User:
    return Depends(require_permission(Permission.CASES_READ.value))


def _read_case() -> CaseAccess:
    return Depends(require_case_access("read"))


@router.get("/cases/{case_id}/bundle")
def bundle(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    path = _bundle_path(case_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No generated bundle yet")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/cases/{case_id}/petition", response_class=PlainTextResponse)
def petition(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> str:
    path = GENERATED_DIR / f"case_{case_id}" / "petition_draft.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No petition yet")
    return path.read_text(encoding="utf-8")


@router.get("/cases/{case_id}/petition/document")
def petition_document(
    case_id: int,
    fmt: str = "pdf",
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
):
    """Download the petition as PDF / DOCX / Markdown.

    Every ``{{placeholder}}`` left over in the source markdown is rewritten
    to ``[TO BE COMPLETED BEFORE FILING]`` before render so the advocate's
    downloaded copy never ships raw template syntax. PDF and DOCX use a
    minimal stdlib renderer (no external deps).
    """
    path = GENERATED_DIR / f"case_{case_id}" / "petition_draft.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No petition yet")
    content = path.read_text(encoding="utf-8")
    return _render_document(
        content, fmt.lower(), base_filename=f"verda_case_{case_id}_petition"
    )


@router.get("/cases/{case_id}/motions/{motion_index}")
def motion_document(
    case_id: int,
    motion_index: int,
    fmt: str = "pdf",
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
):
    """Download a single drafted motion (Notice of Motion / Affidavit /
    List of Authorities) as PDF / DOCX / Markdown.

    The motion list is the one already serialised in ``procedural_engine.json``
    by the orchestrator. Index is 0-based; 404 when out of range.
    """
    procedural_path = GENERATED_DIR / f"case_{case_id}" / "procedural_engine.json"
    if not procedural_path.exists():
        raise HTTPException(status_code=404, detail="No drafted motions yet")
    payload = json.loads(procedural_path.read_text(encoding="utf-8"))
    motions = payload.get("drafted_motions") or []
    if motion_index < 0 or motion_index >= len(motions):
        raise HTTPException(status_code=404, detail=f"Motion #{motion_index} not found")
    motion = motions[motion_index]
    content = motion.get("content") or ""
    slug = (motion.get("filing") or motion.get("template") or f"motion_{motion_index}")
    slug = "".join(
        ch if (ch.isalnum() or ch in "._-") else "_" for ch in slug.strip().lower()
    )
    return _render_document(
        content, fmt.lower(), base_filename=f"verda_case_{case_id}_{slug}"
    )


@router.get("/cases/{case_id}/timeline")
def timeline(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    path = GENERATED_DIR / f"case_{case_id}" / "evidence_codex.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No timeline yet")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/cases/{case_id}/precedents")
def precedents(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    path = GENERATED_DIR / f"case_{case_id}" / "precedent_linker.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No precedents yet")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/cases/{case_id}/procedure")
def procedure(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    path = GENERATED_DIR / f"case_{case_id}" / "procedural_engine.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No procedural engine yet")
    return json.loads(path.read_text(encoding="utf-8"))
