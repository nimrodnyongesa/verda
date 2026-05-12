from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config as _config
from .config import ensure_directories


SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    jurisdiction TEXT NOT NULL DEFAULT 'ke',
    legal_track TEXT NOT NULL DEFAULT 'article_22_petition',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'intake',
    filing_deadline_date TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    evidence_kind TEXT NOT NULL DEFAULT 'unknown',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    extracted_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_case_files_case_id ON case_files(case_id);

CREATE TABLE IF NOT EXISTS toolkit_plans (
    case_id INTEGER PRIMARY KEY,
    plan_json TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    generator_mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_seconds REAL,
    status TEXT NOT NULL DEFAULT 'running',
    bundle_path TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_generation_runs_case_id ON generation_runs(case_id);

CREATE TABLE IF NOT EXISTS generation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    file_path TEXT,
    delay_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES generation_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_generation_events_run_id ON generation_events(run_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_case_id ON audit_log(case_id);

CREATE TABLE IF NOT EXISTS case_members (
    case_id INTEGER NOT NULL,
    user_sub TEXT NOT NULL,
    user_email TEXT,
    user_name TEXT,
    role TEXT NOT NULL DEFAULT 'collaborator',
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    PRIMARY KEY (case_id, user_sub),
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_case_members_case_id ON case_members(case_id);
CREATE INDEX IF NOT EXISTS idx_case_members_user_sub ON case_members(user_sub);

CREATE TABLE IF NOT EXISTS case_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    owner_sub TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES case_folders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_case_folders_parent_id ON case_folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_case_folders_owner_sub ON case_folders(owner_sub);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_sub TEXT PRIMARY KEY,
    display_name TEXT,
    bio TEXT,
    avatar_path TEXT,
    avatar_mime TEXT,
    avatar_version INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


# `cases.folder_id` was added after the original schema. SQLite's
# `IF NOT EXISTS` does not extend to columns, so we add the column lazily on
# first connection if it is missing. This keeps existing DBs healing in
# place without requiring a destructive re-init.
_LAZY_COLUMNS: list[tuple[str, str, str]] = [
    ("cases", "folder_id", "ALTER TABLE cases ADD COLUMN folder_id INTEGER"),
]


def _ensure_lazy_columns(conn: sqlite3.Connection) -> None:
    for table, column, sql in _LAZY_COLUMNS:
        try:
            existing = {
                row.get("name") if isinstance(row, dict) else row[1]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
        except sqlite3.Error:
            continue
        if column in existing:
            continue
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            # Race: another connection added it first. PRAGMA on next call
            # will report the column, so this is a no-op in practice.
            pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=False, default=str)


def loads_json(raw: str | None) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


_initialised_for: str | None = None


def _current_db_path() -> str:
    """Resolve the DB path at call time rather than import time.

    The path is read fresh from `wakili.config` so test-suite reloads (which
    swap the runtime dir) and ad-hoc env-var overrides take effect immediately.
    """
    return str(_config.DB_PATH)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotently create the schema. Free if every table already exists."""
    conn.executescript(SCHEMA)
    _ensure_lazy_columns(conn)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a configured sqlite3 connection.

    The schema is auto-installed on first use against a given DB path. This
    means a fresh runtime directory (e.g. after `make clean`) self-heals on
    the next request without needing a server restart.
    """
    global _initialised_for
    ensure_directories()
    db_path = _current_db_path()
    conn = sqlite3.connect(db_path, isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = _dict_row  # type: ignore[assignment]
    if _initialised_for != db_path:
        try:
            _ensure_schema(conn)
            _initialised_for = db_path
        except sqlite3.Error:
            # Still let callers attempt their query — they'll surface the
            # underlying error themselves if the install genuinely failed.
            pass
    try:
        yield conn
    finally:
        conn.close()


def _dict_row(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def initialize_db() -> None:
    """Install the schema. Idempotent — every CREATE is `IF NOT EXISTS`."""
    global _initialised_for
    ensure_directories()
    with get_connection() as conn:
        _ensure_schema(conn)
        _initialised_for = _current_db_path()
