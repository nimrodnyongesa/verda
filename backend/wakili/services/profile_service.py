"""User profile storage — display name, bio, avatar binary.

Profiles are keyed by ``user_sub`` (the Keycloak / IdP subject claim).
Identity (sub, email, realm roles) still comes from the OIDC token on
every request; this table just holds the per-user *preferences* and the
avatar binary path. That keeps Keycloak as the source of truth for
authentication while letting users customise the local UI.
"""
from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import Any

from ..config import AVATARS_DIR, ensure_directories
from ..db import dumps_json, get_connection, loads_json, utc_now

ALLOWED_AVATAR_MIME: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB — defenders are on slow networks.


def _row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = loads_json(item.pop("metadata_json", "{}"))
    return item


def _safe_sub(sub: str) -> str:
    """Map a sub to a filesystem-safe slug (Keycloak subs are UUIDs but
    federated logins can include slashes / colons)."""
    return hashlib.sha256(sub.encode("utf-8")).hexdigest()[:24]


def get_profile(user_sub: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_sub = ?", (user_sub,)
        ).fetchone()
    return _row(row) if row else None


def upsert_profile(
    user_sub: str,
    *,
    display_name: str | None = None,
    bio: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert or update a profile row. Only fields explicitly passed are
    written — pass ``None`` to leave a field untouched.

    Returns the post-write row.
    """
    now = utc_now()
    existing = get_profile(user_sub)
    fields = {
        "display_name": display_name if display_name is not None else (existing or {}).get("display_name"),
        "bio": bio if bio is not None else (existing or {}).get("bio"),
        "metadata_json": dumps_json(
            metadata if metadata is not None else (existing or {}).get("metadata") or {}
        ),
    }
    with get_connection() as conn:
        if existing:
            conn.execute(
                """
                UPDATE user_profiles
                   SET display_name = ?,
                       bio = ?,
                       metadata_json = ?,
                       updated_at = ?
                 WHERE user_sub = ?
                """,
                (fields["display_name"], fields["bio"], fields["metadata_json"], now, user_sub),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_profiles
                    (user_sub, display_name, bio, avatar_path, avatar_mime,
                     avatar_version, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, NULL, NULL, 0, ?, ?, ?)
                """,
                (user_sub, fields["display_name"], fields["bio"], fields["metadata_json"], now, now),
            )
    profile = get_profile(user_sub)
    assert profile is not None
    return profile


def save_avatar(user_sub: str, content: bytes, mime_type: str) -> dict[str, Any]:
    """Write an avatar to ``runtime/avatars/`` and update the row.

    The previous avatar (if any) is removed atomically — we write the new
    file first, then unlink the old one — so a partial failure leaves a
    valid file behind. ``avatar_version`` is bumped so the frontend can
    cache-bust by adding ``?v=<n>``.
    """
    if mime_type not in ALLOWED_AVATAR_MIME:
        raise ValueError(
            "Avatar must be PNG / JPEG / WebP / GIF / SVG. Got: " + mime_type
        )
    if len(content) > MAX_AVATAR_BYTES:
        raise ValueError(
            f"Avatar exceeds 2 MB (got {len(content) // 1024} KB). Crop or compress."
        )
    if not content:
        raise ValueError("Avatar payload is empty.")

    ensure_directories()
    ext = ALLOWED_AVATAR_MIME[mime_type]
    safe = _safe_sub(user_sub)
    new_path = AVATARS_DIR / f"{safe}_{secrets.token_hex(4)}{ext}"
    new_path.write_bytes(content)

    existing = get_profile(user_sub)
    if not existing:
        upsert_profile(user_sub)
        existing = get_profile(user_sub)
    assert existing is not None

    old_path = existing.get("avatar_path")
    next_version = int(existing.get("avatar_version") or 0) + 1
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE user_profiles
               SET avatar_path = ?,
                   avatar_mime = ?,
                   avatar_version = ?,
                   updated_at = ?
             WHERE user_sub = ?
            """,
            (str(new_path), mime_type, next_version, now, user_sub),
        )

    if old_path:
        try:
            old = Path(old_path)
            if old.exists() and old.parent == AVATARS_DIR:
                old.unlink()
        except OSError:
            # Best-effort — orphaned files in the avatars dir are harmless.
            pass

    profile = get_profile(user_sub)
    assert profile is not None
    return profile


def delete_avatar(user_sub: str) -> dict[str, Any] | None:
    profile = get_profile(user_sub)
    if not profile or not profile.get("avatar_path"):
        return profile
    avatar_path = Path(profile["avatar_path"])
    if avatar_path.exists() and avatar_path.parent == AVATARS_DIR:
        try:
            avatar_path.unlink()
        except OSError:
            pass
    now = utc_now()
    next_version = int(profile.get("avatar_version") or 0) + 1
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE user_profiles
               SET avatar_path = NULL,
                   avatar_mime = NULL,
                   avatar_version = ?,
                   updated_at = ?
             WHERE user_sub = ?
            """,
            (next_version, now, user_sub),
        )
    return get_profile(user_sub)


def load_avatar(user_sub: str) -> tuple[bytes, str] | None:
    """Return ``(bytes, mime)`` for the user's avatar, or None if unset."""
    profile = get_profile(user_sub)
    if not profile or not profile.get("avatar_path"):
        return None
    path = Path(profile["avatar_path"])
    if not path.exists():
        return None
    return path.read_bytes(), profile.get("avatar_mime") or "application/octet-stream"


__all__ = [
    "get_profile",
    "upsert_profile",
    "save_avatar",
    "delete_avatar",
    "load_avatar",
    "ALLOWED_AVATAR_MIME",
    "MAX_AVATAR_BYTES",
]
