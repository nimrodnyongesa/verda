"""Auth-related read endpoints (provider listing + whoami + permissions)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import OIDCProvider, current_user, list_providers
from ..auth.dependencies import User
from ..auth.permissions import (
    list_role_matrix,
    user_permissions,
    has_global_case_scope,
)

router = APIRouter()


def _public(p: OIDCProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "issuer": p.issuer,
        "description": p.description,
    }


@router.get("/auth/providers")
def providers() -> dict:
    return {"providers": [_public(p) for p in list_providers()]}


@router.get("/auth/whoami")
def whoami(user: User = Depends(current_user)) -> dict:
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "anonymous": user.sub == "anonymous",
        "permissions": sorted(p.value for p in user_permissions(user)),
        "global_case_scope": has_global_case_scope(user),
    }


@router.get("/auth/permissions")
def permissions(user: User = Depends(current_user)) -> dict:
    """Effective permissions for the current user + the role matrix.

    The frontend reads this once on mount and uses it to gate UI affordances
    (hide buttons the user cannot trigger). Backend routes still enforce on
    every request — the UI flag is purely cosmetic.

    Shape mirrors the frontend ``PermissionsPayload`` type: a flat record
    so the React provider can consume it without unwrapping.
    """
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "permissions": sorted(p.value for p in user_permissions(user)),
        "global_case_scope": has_global_case_scope(user),
        "anonymous": user.sub == "anonymous",
        "role_matrix": list_role_matrix(),
    }
