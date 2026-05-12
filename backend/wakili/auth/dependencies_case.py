"""Per-case access dependencies that route handlers compose with permissions.

These live in their own module to avoid an import cycle (the access module
needs to read DB + know about User; the dependencies module needs the
auth-flag check from environment).
"""
from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException

from .access import CaseAccess, case_access
from .dependencies import User, current_user


def require_case_access(
    level: Literal["read", "write", "share", "delete"] = "read",
):
    """Factory: assert the user can access the case at the requested level.

    Returns the CaseAccess object so handlers can introspect *how* the user
    has access (owner/global/member) without re-querying.

    Always 404 (not 403) when the user has no access at all — that prevents
    enumeration of case ids the user does not own.
    """

    def _dep(case_id: int, user: User = Depends(current_user)) -> CaseAccess:
        access = case_access(user, case_id)
        if access is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if level == "read" and not access.can_read:
            raise HTTPException(status_code=404, detail="Case not found")
        if level == "write" and not access.can_write:
            raise HTTPException(
                status_code=403, detail="Read-only access to this case"
            )
        if level == "share" and not access.can_share:
            raise HTTPException(
                status_code=403, detail="Sharing is restricted to the case owner"
            )
        if level == "delete" and not access.can_delete:
            raise HTTPException(
                status_code=403, detail="Only the case owner can delete this case"
            )
        return access

    return _dep
