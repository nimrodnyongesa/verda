"""Permission registry and role-to-permission mapping.

Verda uses a coarse RBAC model. The realm assigns a small set of roles to
each user (typically one of: ``admin``, ``lawyer``, ``paralegal``,
``viewer``, ``auditor``); that role expands here to a concrete set of
permissions. Routes depend on those permissions, not the role name, so
adding a new role is one line in ``ROLE_PERMISSIONS`` and zero changes to
the API surface.

Two scoping concepts:

* ``has_permission(user, perm)`` — does the user's role-set carry this permission?
* ``has_global_case_scope(user)`` — is the user allowed to see every case?
  Otherwise, case-level access is gated by ownership or explicit membership
  (see ``access.case_access``).
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from .dependencies import User


class Permission(str, Enum):
    """Canonical permission names the API routes depend on."""

    # Cases — coarse CRUD + sharing
    CASES_READ = "cases:read"
    CASES_CREATE = "cases:create"
    CASES_WRITE = "cases:write"
    CASES_DELETE = "cases:delete"
    CASES_SHARE = "cases:share"

    # Plan + generation gates (lawyer-in-the-loop boundary)
    PLAN_APPROVE = "plan:approve"
    GENERATION_RUN = "generation:run"

    # Export targets — encrypted is privileged because it produces a
    # transportable copy of the bundle.
    EXPORTS_BASIC = "exports:basic"
    EXPORTS_ENCRYPTED = "exports:encrypted"

    # Audit
    AUDIT_CASE = "audit:case"
    AUDIT_GLOBAL = "audit:global"

    # User / membership administration
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"


ALL_PERMISSIONS: set[Permission] = set(Permission)


# Role → permission set. The matrix is the source of truth for what each
# role is allowed to do. The role "anonymous" is the implicit fallback when
# WAKILI_AUTH_ENABLED=false; it carries every permission so the local demo
# stays usable, but the case-level access layer still applies.
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "anonymous": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS,
    "auditor": {
        Permission.CASES_READ,
        Permission.AUDIT_CASE,
        Permission.AUDIT_GLOBAL,
        Permission.USERS_READ,
    },
    "lawyer": {
        Permission.CASES_READ,
        Permission.CASES_CREATE,
        Permission.CASES_WRITE,
        Permission.CASES_SHARE,
        Permission.PLAN_APPROVE,
        Permission.GENERATION_RUN,
        Permission.EXPORTS_BASIC,
        Permission.EXPORTS_ENCRYPTED,
        Permission.AUDIT_CASE,
        Permission.USERS_READ,
    },
    # Paralegals can do most case work but cannot APPROVE filings (the
    # lawyer-in-the-loop principle) and cannot ship encrypted bundles
    # off-platform — that's an explicit lawyer responsibility.
    "paralegal": {
        Permission.CASES_READ,
        Permission.CASES_CREATE,
        Permission.CASES_WRITE,
        Permission.GENERATION_RUN,
        Permission.EXPORTS_BASIC,
        Permission.AUDIT_CASE,
        Permission.USERS_READ,
    },
    "viewer": {
        Permission.CASES_READ,
        Permission.AUDIT_CASE,
    },
}


# Roles that get global read access to every case in the instance. Other
# users see only cases they own or are members of.
#
# ``anonymous`` is included so the local-only mode (WAKILI_AUTH_ENABLED=false)
# behaves like a single-tenant install: there are no other users to scope
# against, so the access layer should be a no-op rather than 404 every case.
GLOBAL_CASE_SCOPE_ROLES: set[str] = {"admin", "auditor", "anonymous"}


def role_permissions(role: str) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def user_permissions(user: User) -> set[Permission]:
    """Union of permissions across the user's roles."""
    if not user.roles:
        # Authenticated but with no role — give them the same surface as
        # ``viewer`` so they can at least see what they have access to.
        return ROLE_PERMISSIONS["viewer"]
    out: set[Permission] = set()
    for role in user.roles:
        out |= ROLE_PERMISSIONS.get(role, set())
    return out


def has_permission(user: User, *perms: Permission | str) -> bool:
    if not perms:
        return True
    granted = user_permissions(user)
    needed = {Permission(p) if isinstance(p, str) else p for p in perms}
    return needed.issubset(granted)


def has_global_case_scope(user: User) -> bool:
    return any(r in GLOBAL_CASE_SCOPE_ROLES for r in user.roles)


def list_role_matrix() -> list[dict]:
    """Snapshot of the role→permission matrix for UI display."""
    return [
        {
            "role": role,
            "permissions": sorted(p.value for p in perms),
            "global_case_scope": role in GLOBAL_CASE_SCOPE_ROLES,
        }
        for role, perms in sorted(ROLE_PERMISSIONS.items())
    ]


def whoami_permissions_payload(user: User) -> dict:
    perms = sorted(p.value for p in user_permissions(user))
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "permissions": perms,
        "global_case_scope": has_global_case_scope(user),
        "anonymous": user.sub == "anonymous",
    }


def to_string_set(perms: Iterable[Permission | str]) -> set[str]:
    return {p.value if isinstance(p, Permission) else p for p in perms}
