"""Profile + avatar endpoints — per-user preferences on top of OIDC.

Auth always reads ``current_user`` so the IdP token is the source of
truth for ``sub`` / ``roles``; the local ``user_profiles`` table just
stores presentation-layer preferences (display name override, bio,
avatar binary).

All endpoints act on the *current* user (``/api/me/...``). Cross-user
profile reads are gated behind ``users:read`` permission so the audit
trail and IAM model stay coherent.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..auth.dependencies import User, current_user, require_permission
from ..auth.permissions import (
    Permission,
    has_global_case_scope,
    user_permissions,
)
from ..services import profile_service
from ..services.audit import record_audit


router = APIRouter()


def _serialise(profile: dict | None, user: User) -> dict:
    """Merge the IdP claims with the local profile row into the shape the
    frontend consumes. ``has_avatar`` lets the UI decide between rendering
    an <img> or the initial-circle fallback without doing a HEAD probe.
    """
    avatar_version = (profile or {}).get("avatar_version") or 0
    has_avatar = bool((profile or {}).get("avatar_path"))
    display_name = (profile or {}).get("display_name") or user.name or user.email or user.sub
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "display_name": display_name,
        "bio": (profile or {}).get("bio") or "",
        "roles": user.roles,
        "permissions": sorted(p.value for p in user_permissions(user)),
        "global_case_scope": has_global_case_scope(user),
        "anonymous": user.sub == "anonymous",
        "has_avatar": has_avatar,
        "avatar_version": avatar_version,
        "avatar_url": f"/api/me/profile/avatar?v={avatar_version}" if has_avatar else None,
        "metadata": (profile or {}).get("metadata") or {},
        "created_at": (profile or {}).get("created_at"),
        "updated_at": (profile or {}).get("updated_at"),
    }


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=1000)


@router.get("/me/profile")
def get_me(user: User = Depends(current_user)) -> dict:
    profile = profile_service.get_profile(user.sub)
    return {"profile": _serialise(profile, user)}


@router.patch("/me/profile")
def patch_me(payload: ProfilePatch, user: User = Depends(current_user)) -> dict:
    """Update display name and / or bio. Identity (sub, email, realm
    roles) cannot be changed here — those flow from the IdP token.
    """
    updates: dict = {}
    if payload.display_name is not None:
        updates["display_name"] = payload.display_name.strip() or None
    if payload.bio is not None:
        updates["bio"] = payload.bio.strip() or None
    if not updates:
        existing = profile_service.get_profile(user.sub)
        return {"profile": _serialise(existing, user), "noop": True}

    profile = profile_service.upsert_profile(user.sub, **updates)
    record_audit(
        actor="lawyer",
        action="profile_updated",
        case_id=None,
        resource=f"user={user.sub}",
        payload={"by": user.sub, "fields": sorted(updates.keys())},
    )
    return {"profile": _serialise(profile, user)}


@router.post("/me/profile/avatar")
async def upload_avatar(
    avatar: UploadFile = File(...),
    user: User = Depends(current_user),
) -> dict:
    if not avatar.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    content = await avatar.read()
    mime = avatar.content_type or "application/octet-stream"
    try:
        profile = profile_service.save_avatar(user.sub, content, mime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        actor="lawyer",
        action="avatar_uploaded",
        case_id=None,
        resource=f"user={user.sub}",
        payload={"by": user.sub, "mime": mime, "bytes": len(content)},
    )
    return {"profile": _serialise(profile, user)}


@router.delete("/me/profile/avatar")
def delete_avatar(user: User = Depends(current_user)) -> dict:
    profile = profile_service.delete_avatar(user.sub)
    record_audit(
        actor="lawyer",
        action="avatar_deleted",
        case_id=None,
        resource=f"user={user.sub}",
        payload={"by": user.sub},
    )
    return {"profile": _serialise(profile, user)}


@router.get("/me/profile/avatar")
def get_my_avatar(user: User = Depends(current_user)) -> Response:
    """Serve the current user's avatar image. The query string
    ``?v=<avatar_version>`` is the cache buster — the route ignores it
    server-side; the integer just changes the URL after every upload so
    browsers don't show a stale image.
    """
    blob = profile_service.load_avatar(user.sub)
    if not blob:
        raise HTTPException(status_code=404, detail="No avatar set")
    body, mime = blob
    return Response(
        content=body,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=300"},
    )


# ---------------------------------------------------------------------------
# Cross-user reads — gated; useful for member lists, audit decoration, etc.
# ---------------------------------------------------------------------------


@router.get("/users/{user_sub}/profile")
def get_user(
    user_sub: str,
    _user: User = Depends(require_permission(Permission.USERS_READ.value)),
) -> dict:
    profile = profile_service.get_profile(user_sub)
    avatar_version = (profile or {}).get("avatar_version") or 0
    has_avatar = bool((profile or {}).get("avatar_path"))
    return {
        "profile": {
            "sub": user_sub,
            "display_name": (profile or {}).get("display_name") or user_sub,
            "bio": (profile or {}).get("bio") or "",
            "has_avatar": has_avatar,
            "avatar_version": avatar_version,
            "avatar_url": f"/api/users/{user_sub}/profile/avatar?v={avatar_version}"
            if has_avatar
            else None,
        }
    }


@router.get("/users/{user_sub}/profile/avatar")
def get_user_avatar(
    user_sub: str,
    _user: User = Depends(require_permission(Permission.USERS_READ.value)),
) -> Response:
    blob = profile_service.load_avatar(user_sub)
    if not blob:
        raise HTTPException(status_code=404, detail="No avatar set")
    body, mime = blob
    return Response(
        content=body,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=300"},
    )
