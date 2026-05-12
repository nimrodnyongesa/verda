from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.access import CaseAccess, case_access
from ..auth.dependencies import User, current_user, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import (
    Permission,
    has_global_case_scope,
    has_permission,
)
from ..mcp import africanlii, case_knowledge, kenyalaw
from ..services.audit import list_audit

router = APIRouter()


@router.get("/mcp/kenyalaw")
def kenyalaw_lookup(
    query: str | None = None,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
) -> dict:
    return {"results": kenyalaw.lookup_judgments(query=query)}


@router.get("/mcp/kenyalaw/{citation}")
def kenyalaw_get(
    citation: str,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
) -> dict:
    j = kenyalaw.get_judgment(citation)
    return {"judgment": j}


@router.get("/mcp/africanlii")
def africanlii_lookup(
    query: str | None = None,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
) -> dict:
    return {"results": africanlii.lookup_judgments(query=query)}


@router.get("/mcp/case-knowledge/{case_id}")
def case_knowledge_list(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    return {"evidence": case_knowledge.list_evidence(case_id)}


@router.get("/mcp/case-knowledge/{case_id}/{file_id}")
def case_knowledge_text(
    case_id: int,
    file_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    return {"text": case_knowledge.get_evidence_text(case_id, file_id)}


@router.get("/audit")
def audit(
    case_id: int | None = None,
    limit: int = 200,
    user: User = Depends(current_user),
) -> dict:
    """Audit log access.

    * No case_id  → requires AUDIT_GLOBAL.
    * With case_id → requires AUDIT_CASE *and* read access to the case
      (owner / member / global-scope role).
    """
    if case_id is None:
        if not has_permission(user, Permission.AUDIT_GLOBAL):
            raise HTTPException(
                status_code=403, detail="Missing permission: audit:global"
            )
        return {"entries": list_audit(case_id=None, limit=limit)}

    if not has_permission(user, Permission.AUDIT_CASE):
        raise HTTPException(status_code=403, detail="Missing permission: audit:case")
    # Reuse the access helper directly so we can return 404 for unknown cases
    # without a separate dependency-shaped redirect.
    if not (
        has_global_case_scope(user)
        or case_access(user, case_id) is not None
    ):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"entries": list_audit(case_id=case_id, limit=limit)}
