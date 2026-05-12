"""Test helpers — shared isolated runtime + sample-case seeder.

Setting env vars at MODULE LOAD TIME (top-level) ensures that any later
``import wakili.config`` picks up the test runtime path. Re-loading config
mid-run would leave already-imported services holding stale path constants.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

# Establish a shared tmp runtime BEFORE wakili is imported by any test.
_RUNTIME = Path(os.environ.get("WAKILI_TEST_RUNTIME") or tempfile.mkdtemp(prefix="wakili-test-"))
os.environ["WAKILI_TEST_RUNTIME"] = str(_RUNTIME)
os.environ["WAKILI_RUNTIME_DIR"] = str(_RUNTIME)
os.environ["WAKILI_DB_PATH"] = str(_RUNTIME / "wakili.db")
# Tests run anonymously by default. The auth-specific tests in test_auth.py
# flip WAKILI_AUTH_ENABLED=true inside individual cases as needed.
os.environ.setdefault("WAKILI_AUTH_ENABLED", "false")

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_case"


def isolated_runtime() -> Path:
    """Ensure runtime dirs exist and the DB schema is initialised."""
    from wakili.config import ensure_directories
    from wakili.db import initialize_db

    ensure_directories()
    initialize_db()
    return _RUNTIME


def cleanup_runtime(_: Path) -> None:
    """No-op: runtime is shared across the test session."""
    return


def seed_test_case(
    *,
    title: str = "Sample protest detentions case",
    description: str = "Composite test fixture — six detained protesters.",
    jurisdiction: str = "ke",
    legal_track: str = "article_22_petition",
) -> dict[str, Any]:
    """Build a fully-formed case from the bundled sample fixture files.

    Mirrors the path a real user takes (create case → upload files → propose
    plan), so any test that wants a populated case can call this without
    coupling to the production code's removed Finance Bill seeder.
    """
    from wakili.services.case_service import create_case, get_case_full
    from wakili.services.intake import add_file, list_files
    from wakili.services.planning import propose_plan, save_plan

    case = create_case(
        {
            "title": title,
            "jurisdiction": jurisdiction,
            "legal_track": legal_track,
            "description": description,
            "metadata": {},
        }
    )
    assert case is not None
    case_id = case["id"]
    for path in sorted(FIXTURE_DIR.iterdir()):
        if not path.is_file():
            continue
        add_file(case_id, path.name, path.read_bytes())
    fresh = get_case_full(case_id)
    assert fresh is not None
    plan = propose_plan(fresh, list_files(case_id))
    save_plan(plan)
    return get_case_full(case_id) or {}


def seed_test_case_via_http(client) -> int:
    """HTTP-shaped variant: returns the new case_id.

    Tests that need to exercise the FastAPI surface call this so requests
    flow through real route handlers (and pick up auth/permission deps).
    """
    case = seed_test_case()
    return case["id"]
