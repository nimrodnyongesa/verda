"""Folder routes — owner-scoped + admin-global hierarchy for cases.

Folders are an IAM-light layer: they belong to a single user (``owner_sub``)
and admins/auditors see all of them via ``has_global_case_scope``. Cases
hold an optional ``folder_id``; moving a case requires write access to the
case AND that the destination folder is one the user can place a case in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.access import CaseAccess
from ..auth.dependencies import User, current_user, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import Permission, has_global_case_scope
from ..services import folder_service
from ..services.audit import record_audit

router = APIRouter()


def _can_manage(folder: dict, user: User) -> bool:
    return has_global_case_scope(user) or folder.get("owner_sub") == user.sub


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    parent_id: int | None = None


class FolderRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class FolderMove(BaseModel):
    parent_id: int | None = None


class CaseMoveRequest(BaseModel):
    folder_id: int | None = None


@router.get("/folders")
def list_folders(
    user: User = Depends(require_permission(Permission.CASES_READ.value)),
) -> dict:
    """Folder tree the user can see. Admins/auditors get every folder.

    Cases that live inside each folder aren't expanded here — the frontend
    fetches `/api/cases` separately and filters by `folder_id`. Keeps each
    response cheap and lets the cases list paginate later without a
    rewrite of this endpoint.
    """
    scope = None if has_global_case_scope(user) else user.sub
    folders = folder_service.list_folders(owner_sub=scope)
    return {"folders": folders}


@router.post("/folders", status_code=201)
def create_folder(
    payload: FolderCreate,
    user: User = Depends(require_permission(Permission.CASES_CREATE.value)),
) -> dict:
    if payload.parent_id is not None:
        parent = folder_service.get_folder(payload.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        if not _can_manage(parent, user):
            raise HTTPException(status_code=403, detail="Cannot nest under that folder")
    try:
        folder = folder_service.create_folder(
            name=payload.name,
            parent_id=payload.parent_id,
            owner_sub=user.sub,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record_audit(
        actor="lawyer",
        action="folder_created",
        case_id=None,
        resource=f"folder={folder['id']}",
        payload={
            "name": folder["name"],
            "parent_id": folder.get("parent_id"),
            "by": user.sub,
        },
    )
    return {"folder": folder}


@router.patch("/folders/{folder_id}")
def patch_folder(
    folder_id: int,
    payload: FolderRename,
    user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
) -> dict:
    folder = folder_service.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if not _can_manage(folder, user):
        raise HTTPException(status_code=403, detail="Cannot rename that folder")
    try:
        updated = folder_service.rename_folder(folder_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Folder not found")
    record_audit(
        actor="lawyer",
        action="folder_renamed",
        case_id=None,
        resource=f"folder={folder_id}",
        payload={"name": updated["name"], "by": user.sub},
    )
    return {"folder": updated}


@router.post("/folders/{folder_id}/move")
def move_folder(
    folder_id: int,
    payload: FolderMove,
    user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
) -> dict:
    folder = folder_service.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if not _can_manage(folder, user):
        raise HTTPException(status_code=403, detail="Cannot move that folder")
    if payload.parent_id is not None:
        parent = folder_service.get_folder(payload.parent_id)
        if not parent or not _can_manage(parent, user):
            raise HTTPException(status_code=404, detail="Target folder not found")
    try:
        updated = folder_service.move_folder(folder_id, payload.parent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Folder not found")
    record_audit(
        actor="lawyer",
        action="folder_moved",
        case_id=None,
        resource=f"folder={folder_id}",
        payload={"parent_id": payload.parent_id, "by": user.sub},
    )
    return {"folder": updated}


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    user: User = Depends(require_permission(Permission.CASES_DELETE.value)),
) -> dict:
    folder = folder_service.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if not _can_manage(folder, user):
        raise HTTPException(
            status_code=403, detail="Only the folder owner can delete it"
        )
    ok = folder_service.delete_folder(folder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Folder not found")
    record_audit(
        actor="lawyer",
        action="folder_deleted",
        case_id=None,
        resource=f"folder={folder_id}",
        payload={"by": user.sub},
    )
    return {"ok": True, "folder_id": folder_id}


# ---------------------------------------------------------------------------
# Case <-> folder
# ---------------------------------------------------------------------------


@router.post("/cases/{case_id}/move")
def move_case(
    case_id: int,
    payload: CaseMoveRequest,
    user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    """Move a case into a folder, or back to the root with ``folder_id: null``.

    Requires write access to the case (existing IAM gate) AND that the
    destination folder is one the caller can place a case in (their own,
    or any folder when admin/auditor).
    """
    if payload.folder_id is not None:
        folder = folder_service.get_folder(payload.folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Target folder not found")
        if not _can_manage(folder, user):
            raise HTTPException(
                status_code=403, detail="Cannot move into a folder you do not own"
            )
    try:
        result = folder_service.move_case(case_id, payload.folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    record_audit(
        actor="lawyer",
        action="case_moved",
        case_id=case_id,
        resource=f"folder={payload.folder_id}",
        payload={"folder_id": payload.folder_id, "by": user.sub},
    )
    return {"case_id": case_id, "folder_id": payload.folder_id}
