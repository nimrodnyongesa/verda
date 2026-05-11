"""FastAPI dependencies for authenticated routes.

Use ``Depends(current_user)`` to require auth (unless WAKILI_AUTH_ENABLED is
false), ``Depends(optional_user)`` for routes that adapt to the caller's
identity but don't require it, and ``Depends(require_user)`` to force auth
even when WAKILI_AUTH_ENABLED is false.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from .oidc import TokenError, verify_token


@dataclass
class User:
    sub: str
    email: str | None
    name: str | None
    roles: list[str]
    raw: dict[str, Any]

    @property
    def display(self) -> str:
        return self.name or self.email or self.sub


# Anonymous user has the synthetic "anonymous" role so the permissions matrix
# resolves to the full surface — anonymous mode is local-only / single-tenant
# and the case-level access layer handles per-case scoping when auth is on.
ANON = User(
    sub="anonymous",
    email=None,
    name="Anonymous",
    roles=["anonymous"],
    raw={},
)


def _auth_enabled() -> bool:
    """Auth is ON by default. Set WAKILI_AUTH_ENABLED=false explicitly to
    bypass — supported for offline / air-gapped CI runs only.
    """
    return os.getenv("WAKILI_AUTH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _user_from_claims(claims: dict[str, Any]) -> User:
    realm = claims.get("realm_access") or {}
    realm_roles = list(realm.get("roles") or [])
    resource_access = claims.get("resource_access") or {}
    resource_roles: list[str] = []
    for entry in resource_access.values():
        if isinstance(entry, dict):
            resource_roles.extend(entry.get("roles") or [])
    standard_roles = list(claims.get("roles") or [])
    merged = sorted({*realm_roles, *resource_roles, *standard_roles})
    return User(
        sub=str(claims.get("sub") or ""),
        email=claims.get("email"),
        name=claims.get("name") or claims.get("preferred_username"),
        roles=merged,
        raw=claims,
    )


def current_user(authorization: str | None = Header(default=None)) -> User:
    """Required-auth dependency. Anonymous when WAKILI_AUTH_ENABLED is false."""
    if not _auth_enabled():
        return ANON
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": 'Bearer realm="wakili"'},
        )
    try:
        claims = verify_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc
    return _user_from_claims(claims)


def optional_user(authorization: str | None = Header(default=None)) -> User:
    """Returns the user when one is present, otherwise ANON. Never raises."""
    if not _auth_enabled():
        return ANON
    token = _extract_token(authorization)
    if not token:
        return ANON
    try:
        claims = verify_token(token)
    except TokenError:
        return ANON
    return _user_from_claims(claims)


def require_user(authorization: str | None = Header(default=None)) -> User:
    """Force auth regardless of WAKILI_AUTH_ENABLED — for sensitive endpoints."""
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    try:
        claims = verify_token(token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _user_from_claims(claims)


def require_role(*roles: str):
    """Factory: depends on current_user and asserts at least one role matches."""

    def _dep(user: User = Depends(current_user)) -> User:
        if not roles:
            return user
        if any(r in user.roles for r in roles):
            return user
        raise HTTPException(status_code=403, detail=f"Missing required role: {' | '.join(roles)}")

    return _dep


def require_permission(*perms: str):
    """Factory: assert the user has every named permission.

    Imported lazily to avoid a circular dependency with ``permissions.py``,
    which imports ``User`` from this module.
    """

    def _dep(user: User = Depends(current_user)) -> User:
        from .permissions import has_permission, Permission  # local import

        missing = [p for p in perms if not has_permission(user, Permission(p))]
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {', '.join(missing)}",
            )
        return user

    return _dep
