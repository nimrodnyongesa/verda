"""Case folders — owner-scoped, arbitrarily nested.

Each folder belongs to a single user (``owner_sub``); admins / auditors
see every folder via the IAM ``GLOBAL_CASE_SCOPE_ROLES`` set. Cases can
optionally be placed inside a folder (``cases.folder_id``); a NULL means
the case lives at the user's root.

Cycle prevention: a folder cannot be reparented under its own descendant.
That check is enforced in ``move_folder``.
"""
from __future__ import annotations

from typing import Any

from ..db import dumps_json, get_connection, loads_json, utc_now


def _row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
    return item


def list_folders(owner_sub: str | None) -> list[dict[str, Any]]:
    """All folders visible to ``owner_sub``. ``None`` means global scope."""
    with get_connection() as conn:
        if owner_sub is None:
            rows = conn.execute(
                "SELECT * FROM case_folders ORDER BY parent_id IS NOT NULL, name COLLATE NOCASE"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM case_folders WHERE owner_sub = ? ORDER BY parent_id IS NOT NULL, name COLLATE NOCASE",
                (owner_sub,),
            ).fetchall()
    return [_row(r) for r in rows]


def get_folder(folder_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM case_folders WHERE id = ?", (folder_id,)
        ).fetchone()
    return _row(row) if row else None


def create_folder(
    *, name: str, parent_id: int | None, owner_sub: str
) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("Folder name cannot be empty")
    if len(name) > 120:
        raise ValueError("Folder name is too long (max 120 chars)")

    if parent_id is not None:
        parent = get_folder(parent_id)
        if not parent:
            raise ValueError("Parent folder does not exist")
        if parent["owner_sub"] != owner_sub:
            # Owners can only nest inside their own folders. Admin global-scope
            # checks happen in the API layer, not here.
            raise ValueError("Cannot create a folder inside a folder you do not own")

    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_folders (name, parent_id, owner_sub, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, parent_id, owner_sub, dumps_json({}), now, now),
        )
        new_id = cursor.lastrowid
    folder = get_folder(int(new_id)) if new_id is not None else None
    assert folder is not None
    return folder


def rename_folder(folder_id: int, new_name: str) -> dict[str, Any] | None:
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Folder name cannot be empty")
    if len(new_name) > 120:
        raise ValueError("Folder name is too long (max 120 chars)")
    now = utc_now()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE case_folders SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, now, folder_id),
        )
        if (cur.rowcount or 0) == 0:
            return None
    return get_folder(folder_id)


def _descendant_ids(folder_id: int) -> set[int]:
    """Collect the folder + all transitive children. Used for cycle checks
    and for cascading deletes."""
    seen: set[int] = {folder_id}
    frontier = [folder_id]
    with get_connection() as conn:
        while frontier:
            row = conn.execute(
                f"SELECT id FROM case_folders WHERE parent_id IN ({','.join('?' * len(frontier))})",
                frontier,
            ).fetchall()
            next_frontier = [r["id"] for r in row if r["id"] not in seen]
            seen.update(next_frontier)
            frontier = next_frontier
    return seen


def move_folder(folder_id: int, new_parent_id: int | None) -> dict[str, Any] | None:
    """Move a folder under another folder (or to root with ``None``).

    Cycle-safe: the new parent cannot be the folder itself or any of its
    descendants. Cross-owner moves are rejected (the caller should already
    have verified ownership before calling).
    """
    folder = get_folder(folder_id)
    if not folder:
        return None
    if new_parent_id is not None:
        if new_parent_id == folder_id:
            raise ValueError("A folder cannot be its own parent")
        descendants = _descendant_ids(folder_id)
        if new_parent_id in descendants:
            raise ValueError("Cannot move a folder into one of its descendants")
        parent = get_folder(new_parent_id)
        if not parent:
            raise ValueError("Target parent folder does not exist")
        if parent["owner_sub"] != folder["owner_sub"]:
            raise ValueError("Cannot move into a folder owned by a different user")
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE case_folders SET parent_id = ?, updated_at = ? WHERE id = ?",
            (new_parent_id, now, folder_id),
        )
    return get_folder(folder_id)


def delete_folder(folder_id: int) -> bool:
    """Remove a folder. Cascades to its children via the FK. Cases inside
    are NOT deleted — their ``folder_id`` is reset to NULL so they remain
    visible at the user's root.
    """
    descendants = _descendant_ids(folder_id)
    if not descendants:
        return False
    placeholders = ",".join("?" * len(descendants))
    with get_connection() as conn:
        conn.execute(
            f"UPDATE cases SET folder_id = NULL WHERE folder_id IN ({placeholders})",
            tuple(descendants),
        )
        cur = conn.execute(
            "DELETE FROM case_folders WHERE id = ?", (folder_id,)
        )
    return (cur.rowcount or 0) > 0


def move_case(case_id: int, folder_id: int | None) -> dict[str, Any] | None:
    """Place a case in a folder, or send it back to the root with ``None``."""
    if folder_id is not None:
        folder = get_folder(folder_id)
        if not folder:
            raise ValueError("Target folder does not exist")
    now = utc_now()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE cases SET folder_id = ?, updated_at = ? WHERE id = ?",
            (folder_id, now, case_id),
        )
        if (cur.rowcount or 0) == 0:
            return None
        row = conn.execute(
            "SELECT id, folder_id FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
    return dict(row) if row else None


def folder_path(folder_id: int) -> list[dict[str, Any]]:
    """Walk from the given folder up to the root, returning [root, …, leaf].

    Useful for breadcrumbs on the frontend.
    """
    chain: list[dict[str, Any]] = []
    current_id: int | None = folder_id
    seen: set[int] = set()
    while current_id is not None:
        if current_id in seen:
            break  # defensive — should never happen because of cycle guard
        seen.add(current_id)
        node = get_folder(current_id)
        if not node:
            break
        chain.append(node)
        current_id = node.get("parent_id")
    chain.reverse()
    return chain


__all__ = [
    "list_folders",
    "get_folder",
    "create_folder",
    "rename_folder",
    "move_folder",
    "delete_folder",
    "move_case",
    "folder_path",
]
