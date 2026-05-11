from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..auth import current_user
from ..auth.access import (
    CASE_ROLES,
    CaseAccess,
    add_member,
    list_members,
    remove_member,
    serialise_access,
    visible_case_ids,
)
from ..auth.dependencies import User, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import Permission
from ..schemas import CaseCreate
from ..services.case_service import (
    create_case,
    get_case_full,
    list_cases,
)
from ..services.intake import add_file
from ..services.planning import propose_plan, save_plan, load_plan, approve_plan

router = APIRouter()


@router.get("/cases")
def list_all(
    user: User = Depends(require_permission(Permission.CASES_READ.value)),
    page: int = 1,
    per_page: int = 25,
    q: str | None = None,
    folder_id: int | None = None,
    root: bool = False,
) -> dict:
    """Cases the user can read, paginated server-side.

    Filters (combined with AND):
      * ``folder_id``  — exact folder match (cases.folder_id == folder_id)
      * ``root=true``  — only cases at the user's root (folder_id IS NULL)
      * ``q``          — case-insensitive substring across title, description,
                         jurisdiction, legal_track, and the folder name path.
                         When ``q`` is set, ``folder_id`` / ``root`` filters
                         are bypassed so search reaches every folder.

    Response shape (additive — old clients that only read ``cases`` keep
    working unchanged):

        { "cases": [...], "page": 1, "per_page": 25, "total": N,
          "total_pages": M }
    """
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))
    visible = visible_case_ids(user)
    cases = list_cases()
    if visible is not None:
        keep = set(visible)
        cases = [c for c in cases if c["id"] in keep]

    if q and q.strip():
        from ..services.folder_service import folder_path

        needle = q.strip().lower()

        def matches(c: dict) -> bool:
            haystacks = [
                str(c.get("title") or ""),
                str(c.get("description") or ""),
                str(c.get("jurisdiction") or ""),
                str(c.get("legal_track") or ""),
            ]
            fid = c.get("folder_id")
            if fid is not None:
                try:
                    chain = folder_path(int(fid))
                    haystacks.append(" / ".join(f["name"] for f in chain))
                except Exception:  # noqa: BLE001 — defensive: bad folder_id
                    pass
            return any(needle in h.lower() for h in haystacks)

        cases = [c for c in cases if matches(c)]
    elif folder_id is not None:
        cases = [c for c in cases if (c.get("folder_id") == folder_id)]
    elif root:
        cases = [c for c in cases if c.get("folder_id") is None]

    total = len(cases)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "cases": cases[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


@router.delete("/cases/{case_id}")
def delete_case(
    case_id: int,
    user: User = Depends(require_permission(Permission.CASES_DELETE.value)),
    access: CaseAccess = Depends(require_case_access("delete")),
) -> dict:
    """Permanently delete a case + every dependent row.

    Authorisation is two-factor: the role must include ``cases:delete`` AND
    the per-case access record must report ``can_delete=true`` (owner or
    global scope only). Cascades via FK to ``case_files``, ``toolkit_plans``,
    ``generation_runs``, ``generation_events``, and ``case_members``. Audit
    rows linked by ``case_id`` are kept (the audit log is append-only).
    """
    from ..db import get_connection
    from ..services.audit import record_audit
    from ..services.case_service import get_case_full

    case = get_case_full(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    record_audit(
        actor="lawyer",
        action="case_deleted",
        case_id=case_id,
        resource=f"case={case_id}",
        payload={"by": user.sub, "title": case.get("title"), "via": access.via},
    )
    with get_connection() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    return {"ok": True, "case_id": case_id}


@router.post("/cases", status_code=201)
def create(
    payload: CaseCreate,
    user: User = Depends(require_permission(Permission.CASES_CREATE.value)),
) -> dict:
    data = payload.model_dump()
    metadata = dict(data.get("metadata") or {})
    metadata["owner_sub"] = user.sub
    metadata["owner_name"] = user.display
    metadata.setdefault("owner_email", user.email)
    data["metadata"] = metadata
    case = create_case(data)
    if not case:
        raise HTTPException(status_code=500, detail="Failed to create case")
    return {"case": case}


@router.get("/cases/{case_id}")
def get_one(
    case_id: int,
    access: CaseAccess = Depends(require_case_access("read")),  # noqa: E251 — fastapi dep
    _: User = Depends(require_permission(Permission.CASES_READ.value)),
) -> dict:
    case = get_case_full(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case["access"] = serialise_access(access)
    return {"case": case}


class CasePatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


@router.patch("/cases/{case_id}")
def patch_case(
    case_id: int,
    payload: CasePatch,
    user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    """Rename the case and/or update its description.

    Other fields (jurisdiction, legal_track, status, metadata) are deliberately
    immutable through this endpoint — those changes go through dedicated flows
    (plan, generation) so audit trails stay clean.
    """
    case = get_case_full(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    fields: dict[str, str] = {}
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        fields["title"] = title
    if payload.description is not None:
        fields["description"] = payload.description.strip()
    if not fields:
        return {"case": case}

    from ..db import get_connection, utc_now
    from ..services.audit import record_audit

    now = utc_now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params: list = list(fields.values()) + [now, case_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE cases SET {set_clause}, updated_at = ? WHERE id = ?",
            tuple(params),
        )

    record_audit(
        actor="lawyer",
        action="patch_case",
        case_id=case_id,
        resource=f"case={case_id}",
        payload={
            "by": user.sub,
            "fields": list(fields.keys()),
            "previous_title": case.get("title"),
            "new_title": fields.get("title", case.get("title")),
        },
    )

    updated = get_case_full(case_id)
    return {"case": updated}


@router.post("/cases/{case_id}/files")
async def upload_files(
    case_id: int,
    files: list[UploadFile],
    _user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    case = get_case_full(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    added = []
    for f in files:
        if not f.filename:
            continue
        content = await f.read()
        added.append(add_file(case_id, f.filename, content, f.content_type))
    return {"case": get_case_full(case_id), "added": added}


@router.post("/cases/{case_id}/plan")
def regenerate_plan(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_WRITE.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    from ..services.intake import list_files

    case = get_case_full(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    files = list_files(case_id)
    plan = propose_plan(case, files)
    save_plan(plan)
    return {"plan": plan}


@router.get("/cases/{case_id}/plan")
def fetch_plan(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    plan = load_plan(case_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan saved for this case")
    return {"plan": plan}


@router.post("/cases/{case_id}/plan/approve")
def approve(
    case_id: int,
    _user: User = Depends(require_permission(Permission.PLAN_APPROVE.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    plan = approve_plan(case_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan to approve")
    return {"plan": plan}


# ---------------------------------------------------------------------------
# Members / sharing
# ---------------------------------------------------------------------------


class MemberAdd(BaseModel):
    user_sub: str = Field(..., min_length=1, max_length=128)
    user_email: str | None = Field(default=None, max_length=200)
    user_name: str | None = Field(default=None, max_length=200)
    role: str = Field(default="collaborator")


@router.get("/cases/{case_id}/members")
def members_list(
    case_id: int,
    _user: User = Depends(require_permission(Permission.USERS_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    return {"members": list_members(case_id), "case_roles": list(CASE_ROLES)}


@router.post("/cases/{case_id}/members", status_code=201)
def members_add(
    case_id: int,
    payload: MemberAdd,
    user: User = Depends(require_permission(Permission.CASES_SHARE.value)),
    _access: CaseAccess = Depends(require_case_access("share")),
) -> dict:
    from ..services.audit import record_audit

    if payload.role not in CASE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(CASE_ROLES)}",
        )
    try:
        member = add_member(
            case_id,
            user_sub=payload.user_sub.strip(),
            user_email=(payload.user_email or "").strip() or None,
            user_name=(payload.user_name or "").strip() or None,
            role=payload.role,
            granted_by=user.sub,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record_audit(
        actor="lawyer",
        action="case_member_added",
        case_id=case_id,
        resource=f"member={payload.user_sub}",
        payload={"role": payload.role, "granted_by": user.sub},
    )
    return {"member": member}


@router.delete("/cases/{case_id}/members/{user_sub}")
def members_remove(
    case_id: int,
    user_sub: str,
    user: User = Depends(require_permission(Permission.CASES_SHARE.value)),
    _access: CaseAccess = Depends(require_case_access("share")),
) -> dict:
    from ..services.audit import record_audit

    if not remove_member(case_id, user_sub):
        raise HTTPException(status_code=404, detail="Member not found on this case")
    record_audit(
        actor="lawyer",
        action="case_member_removed",
        case_id=case_id,
        resource=f"member={user_sub}",
        payload={"removed_by": user.sub},
    )
    return {"ok": True, "case_id": case_id, "user_sub": user_sub}
