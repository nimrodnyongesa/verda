"""Per-case access control.

A user can access a case if any of these is true:
  1. They have global case scope (admin, auditor).
  2. They are the case's owner (``metadata.owner_sub`` matches ``user.sub``).
  3. They have an explicit membership row in ``case_members``.

A membership grants one of the levels:
  - ``owner``      — full read + write + share + delete
  - ``collaborator`` — read + write
  - ``viewer``     — read-only

Access is also overridable at the route level by the role-based permissions
in ``permissions.py``: e.g. ``viewer`` membership cannot upload files because
``cases:write`` requires both the role-level permission AND a write-level
membership.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..db import dumps_json, get_connection, loads_json, utc_now
from .dependencies import User
from .permissions import has_global_case_scope


CaseRole = Literal["owner", "collaborator", "viewer"]
CASE_ROLES: tuple[CaseRole, ...] = ("owner", "collaborator", "viewer")
WRITE_LEVELS: set[CaseRole] = {"owner", "collaborator"}
SHARE_LEVELS: set[CaseRole] = {"owner"}


@dataclass(frozen=True)
class CaseAccess:
    """Result of a case-access check."""

    case_id: int
    user_sub: str
    via: Literal["global", "owner", "member"]
    role: CaseRole

    @property
    def can_read(self) -> bool:
        return True

    @property
    def can_write(self) -> bool:
        return self.role in WRITE_LEVELS

    @property
    def can_share(self) -> bool:
        return self.via in {"global", "owner"} or self.role in SHARE_LEVELS

    @property
    def can_delete(self) -> bool:
        return self.via == "global" or self.role == "owner"


def _case_owner_sub(case_id: int) -> tuple[bool, str | None]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
    if not row:
        return (False, None)
    meta = loads_json(row.get("metadata_json"))
    return (True, meta.get("owner_sub"))


def case_access(user: User, case_id: int) -> CaseAccess | None:
    """Return the access record for a user against a case, or None.

    Returns None when:
      - the case does not exist, OR
      - the user has no role-level scope, no ownership, and no membership.
    """
    exists, owner_sub = _case_owner_sub(case_id)
    if not exists:
        return None
    if has_global_case_scope(user):
        return CaseAccess(case_id=case_id, user_sub=user.sub, via="global", role="owner")
    if owner_sub and owner_sub == user.sub:
        return CaseAccess(case_id=case_id, user_sub=user.sub, via="owner", role="owner")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role FROM case_members WHERE case_id = ? AND user_sub = ?",
            (case_id, user.sub),
        ).fetchone()
    if not row:
        return None
    role = row.get("role")
    if role not in CASE_ROLES:
        role = "viewer"
    return CaseAccess(case_id=case_id, user_sub=user.sub, via="member", role=role)


def visible_case_ids(user: User) -> list[int] | None:
    """Return a list of case ids the user can READ, or None for "no filter".

    None means "no scoping" — used by callers as a hint to skip the WHERE
    clause when the user has global scope.
    """
    if has_global_case_scope(user):
        return None
    with get_connection() as conn:
        owned = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM cases WHERE json_extract(metadata_json,'$.owner_sub') = ?",
                (user.sub,),
            ).fetchall()
        ]
        members = [
            r["case_id"]
            for r in conn.execute(
                "SELECT case_id FROM case_members WHERE user_sub = ?",
                (user.sub,),
            ).fetchall()
        ]
    seen: set[int] = set()
    out: list[int] = []
    for cid in [*owned, *members]:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def list_members(case_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM case_members WHERE case_id = ? ORDER BY granted_at ASC",
            (case_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_member(
    case_id: int,
    *,
    user_sub: str,
    user_email: str | None,
    user_name: str | None,
    role: str,
    granted_by: str,
) -> dict:
    if role not in CASE_ROLES:
        raise ValueError(f"invalid case role: {role!r} (allowed: {', '.join(CASE_ROLES)})")
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO case_members (case_id, user_sub, user_email, user_name, role, granted_by, granted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, user_sub) DO UPDATE SET
                user_email = excluded.user_email,
                user_name = excluded.user_name,
                role = excluded.role,
                granted_by = excluded.granted_by,
                granted_at = excluded.granted_at
            """,
            (case_id, user_sub, user_email, user_name, role, granted_by, now),
        )
        row = conn.execute(
            "SELECT * FROM case_members WHERE case_id = ? AND user_sub = ?",
            (case_id, user_sub),
        ).fetchone()
    return dict(row)


def remove_member(case_id: int, user_sub: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM case_members WHERE case_id = ? AND user_sub = ?",
            (case_id, user_sub),
        )
        return (cur.rowcount or 0) > 0


def serialise_access(access: CaseAccess | None) -> dict | None:
    if not access:
        return None
    return {
        "case_id": access.case_id,
        "user_sub": access.user_sub,
        "via": access.via,
        "role": access.role,
        "can_read": access.can_read,
        "can_write": access.can_write,
        "can_share": access.can_share,
        "can_delete": access.can_delete,
    }


__all__ = [
    "CaseAccess",
    "CASE_ROLES",
    "case_access",
    "visible_case_ids",
    "list_members",
    "add_member",
    "remove_member",
    "serialise_access",
    "dumps_json",  # re-exported for convenience by callers
]
