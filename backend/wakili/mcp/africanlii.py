"""africanlii-mcp — stub server for AfricanLII regional case law.

The MVP corpus is empty. This stub returns no results but records the call so
the audit log shows where the lawyer should expand jurisdictional coverage.
"""
from __future__ import annotations

from typing import Any

from ..services.audit import record_audit


def lookup_judgments(jurisdiction: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
    record_audit(
        actor="africanlii-mcp",
        action="lookup_judgments",
        resource=f"jurisdiction={jurisdiction or '*'};query={query or '*'}",
        payload={"jurisdiction": jurisdiction, "query": query, "note": "MVP corpus empty"},
    )
    return []
