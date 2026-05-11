"""Verda MCP server implementation.

Wires every Verda domain operation behind an MCP ``Tool`` so an LLM agent
can drive the platform end-to-end. The server speaks JSON-RPC over stdio
by default (the form Claude Desktop / Claude Code use); a process
launching the server gets full domain control as the configured user.

Authentication model
--------------------
The MCP server runs *in-process* with the same auth flag the HTTP API
respects (``WAKILI_AUTH_ENABLED``). When auth is on, set
``VERDA_MCP_USER_SUB`` (and optionally ``VERDA_MCP_USER_ROLES``) so the
in-process call mimics a signed-in user. When auth is off (local-only
mode), the synthetic ``anonymous`` user is used and every tool succeeds.

This means MCP clients running on the same host can drive a private
Verda instance without exchanging cookies; they inherit the OS-level
trust boundary the operator already grants by launching the process.
"""
from __future__ import annotations

import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from ..auth.dependencies import ANON, User
from ..auth.permissions import has_global_case_scope
from ..db import initialize_db
from ..services import folder_service
from ..services.audit import list_audit, record_audit
from ..services.case_service import (
    create_case,
    get_case_full,
    list_cases,
    list_files,
)
from ..services.orchestrator import latest_run, list_events, list_runs, run_generation
from ..services.planning import approve_plan, load_plan, propose_plan, save_plan
from ..services.intake import list_files as list_files_intake


SERVER_NAME = "verda"
SERVER_VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# User-identity shim
# ---------------------------------------------------------------------------


def _current_user() -> User:
    """Resolve the user the MCP session acts as.

    Priority:
      1. ``WAKILI_AUTH_ENABLED=false`` → synthetic anonymous (full perms).
      2. ``VERDA_MCP_USER_SUB`` set → mint a User with the listed roles
         (``VERDA_MCP_USER_ROLES`` is a comma-separated list, default
         ``lawyer``).
      3. Otherwise fall back to anonymous.

    The user record is used purely for audit attribution and case-scope
    filtering; signature verification is bypassed because the caller is
    already on the host where the server runs.
    """
    auth_on = os.getenv("WAKILI_AUTH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not auth_on:
        return ANON
    sub = os.getenv("VERDA_MCP_USER_SUB")
    if not sub:
        return ANON
    roles_raw = os.getenv("VERDA_MCP_USER_ROLES", "lawyer")
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
    if not roles:
        roles = ["lawyer"]
    return User(
        sub=sub,
        email=os.getenv("VERDA_MCP_USER_EMAIL"),
        name=os.getenv("VERDA_MCP_USER_NAME") or sub,
        roles=roles,
        raw={},
    )


def _visible_case_ids(user: User) -> set[int] | None:
    """Mirror of ``auth.access.visible_case_ids`` but local to avoid an
    import cycle with the FastAPI dep tree."""
    from ..auth.access import visible_case_ids

    ids = visible_case_ids(user)
    return set(ids) if ids is not None else None


def _ok(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, indent=2))]


def _err(message: str, *, code: str = "verda_error") -> list[TextContent]:
    return [
        TextContent(
            type="text",
            text=json.dumps({"error": code, "message": message}, indent=2),
        )
    ]


# ---------------------------------------------------------------------------
# Tool catalog — every entry has a JSON Schema for the input. Returning a
# typed list lets MCP clients (and Anthropic's tool-use models) generate
# the right call shape without trial-and-error.
# ---------------------------------------------------------------------------


def _tools() -> list[Tool]:
    return [
        # ---------------- Cases ----------------
        Tool(
            name="cases.list",
            description=(
                "List cases the current user can read. Supports pagination, "
                "search, and folder scoping. Use this before any per-case "
                "operation so the caller knows valid case IDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
                    "q": {"type": "string", "description": "Search across title, description, jurisdiction, legal_track, and folder path."},
                    "folder_id": {"type": ["integer", "null"], "description": "Restrict to a specific folder. Null/omitted = all the user can see."},
                    "root_only": {"type": "boolean", "default": False, "description": "Restrict to cases not in any folder."},
                },
            },
        ),
        Tool(
            name="cases.get",
            description="Fetch a single case with files, plan status, and latest run.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="cases.create",
            description="Create a new case. Stamps the caller as owner.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                    "jurisdiction": {"type": "string", "default": "ke"},
                    "legal_track": {"type": "string", "default": "article_22_petition"},
                    "description": {"type": "string", "default": ""},
                    "folder_id": {"type": ["integer", "null"]},
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="cases.patch",
            description="Update title and/or description of an existing case.",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "integer"},
                    "title": {"type": "string", "maxLength": 200},
                    "description": {"type": "string", "maxLength": 4000},
                },
                "required": ["case_id"],
            },
        ),
        Tool(
            name="cases.delete",
            description="Permanently delete a case and all dependent rows. Audit log entries are retained.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="cases.move",
            description="Move a case into a folder, or back to root with folder_id=null.",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "integer"},
                    "folder_id": {"type": ["integer", "null"]},
                },
                "required": ["case_id"],
            },
        ),
        Tool(
            name="cases.files",
            description="List uploaded evidence files attached to a case (no extracted text — fetch via outputs.timeline for parsed events).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        # ---------------- Folders ----------------
        Tool(
            name="folders.list",
            description="List folders visible to the user. Admin / auditor see every folder; everyone else sees folders they own.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="folders.create",
            description="Create a folder at root or nested under another folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "parent_id": {"type": ["integer", "null"]},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="folders.rename",
            description="Rename a folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_id": {"type": "integer"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                },
                "required": ["folder_id", "name"],
            },
        ),
        Tool(
            name="folders.move",
            description="Re-parent a folder. Cycle-safe — the new parent cannot be a descendant.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_id": {"type": "integer"},
                    "parent_id": {"type": ["integer", "null"]},
                },
                "required": ["folder_id"],
            },
        ),
        Tool(
            name="folders.delete",
            description="Delete a folder. Subfolders cascade-delete; cases inside fall back to root.",
            inputSchema={
                "type": "object",
                "properties": {"folder_id": {"type": "integer"}},
                "required": ["folder_id"],
            },
        ),
        # ---------------- Plan / generation ----------------
        Tool(
            name="plan.get",
            description="Fetch the saved plan for a case.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="plan.regenerate",
            description="Re-run the planner using current evidence; resets approval status.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="plan.approve",
            description="Mark the plan as approved by a lawyer (required gate before generation runs).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="generation.run",
            description="Run the toolkit generator. Plan must be approved. Returns a run summary.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="generation.runs",
            description="List previous generation runs for a case.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="generation.events",
            description="List the Codex agent stream events for a specific run id.",
            inputSchema={
                "type": "object",
                "properties": {"run_id": {"type": "integer"}},
                "required": ["run_id"],
            },
        ),
        Tool(
            name="generation.latest",
            description="Latest generation run for a case (with its event stream).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        # ---------------- Outputs ----------------
        Tool(
            name="outputs.bundle",
            description="Return the final bundle.json for a generated case.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="outputs.petition",
            description="Return the drafted petition (markdown).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="outputs.timeline",
            description="Return the Evidence Codex timeline JSON.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="outputs.precedents",
            description="Return the Precedent Linker JSON (Kenya Law authorities, ranked).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="outputs.procedure",
            description="Return the Procedural Engine JSON (state machine, deadlines, drafted motions).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        # ---------------- Exports ----------------
        Tool(
            name="exports.zip",
            description="Build a flat zip bundle and return its absolute path on disk.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="exports.encrypted",
            description="Build an AES-256-GCM encrypted bundle (with the bundled stdlib decrypter) and return its path. Requires a passphrase ≥ 8 chars.",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "integer"},
                    "passphrase": {"type": "string", "minLength": 8},
                },
                "required": ["case_id", "passphrase"],
            },
        ),
        Tool(
            name="exports.docker",
            description="Build a self-hosted Docker viewer tarball and return its path.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="exports.usb",
            description="Build a USB-portable viewer zip and return its path.",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        # ---------------- Audit ----------------
        Tool(
            name="audit.list",
            description="Return the audit log. Filter by case_id when scoping; cap at `limit` rows (default 200).",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": ["integer", "null"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
                },
            },
        ),
        # ---------------- MCP knowledge servers ----------------
        Tool(
            name="kenyalaw.search",
            description="Query the bundled Kenya Law judgment corpus via Verda's kenyalaw-mcp adapter. Every URL returned is a real, verified kenyalaw.org URL.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        ),
        Tool(
            name="kenyalaw.get",
            description="Fetch one Kenya Law judgment by citation.",
            inputSchema={
                "type": "object",
                "properties": {"citation": {"type": "string"}},
                "required": ["citation"],
            },
        ),
        Tool(
            name="case_knowledge.list",
            description="List the per-case knowledge index (evidence files + metadata).",
            inputSchema={
                "type": "object",
                "properties": {"case_id": {"type": "integer"}},
                "required": ["case_id"],
            },
        ),
        Tool(
            name="case_knowledge.text",
            description="Fetch the extracted full text of a single evidence file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "integer"},
                    "file_id": {"type": "integer"},
                },
                "required": ["case_id", "file_id"],
            },
        ),
        # ---------------- Permissions / introspection ----------------
        Tool(
            name="iam.whoami",
            description="Identity, roles, effective permissions, and global-case-scope of the current MCP session.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="iam.role_matrix",
            description="The full role → permission matrix Verda enforces.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _dispatch(name: str, args: dict[str, Any]) -> list[TextContent]:  # noqa: C901
    user = _current_user()
    visible_ids = _visible_case_ids(user)

    def _ensure_case_visible(case_id: int) -> dict | None:
        if visible_ids is not None and case_id not in visible_ids:
            return None
        return get_case_full(case_id)

    try:
        if name == "iam.whoami":
            from ..auth.permissions import user_permissions

            return _ok(
                {
                    "sub": user.sub,
                    "email": user.email,
                    "name": user.name,
                    "roles": user.roles,
                    "permissions": sorted(p.value for p in user_permissions(user)),
                    "global_case_scope": has_global_case_scope(user),
                    "anonymous": user.sub == "anonymous",
                }
            )
        if name == "iam.role_matrix":
            from ..auth.permissions import list_role_matrix

            return _ok({"roles": list_role_matrix()})

        # ---- Cases ----
        if name == "cases.list":
            page = max(1, int(args.get("page", 1)))
            per_page = max(1, min(100, int(args.get("per_page", 25))))
            cases = list_cases()
            if visible_ids is not None:
                cases = [c for c in cases if c["id"] in visible_ids]
            q = (args.get("q") or "").strip().lower()
            folder_id = args.get("folder_id")
            root_only = bool(args.get("root_only"))
            if q:
                cases = [
                    c
                    for c in cases
                    if q in str(c.get("title") or "").lower()
                    or q in str(c.get("description") or "").lower()
                    or q in str(c.get("legal_track") or "").lower()
                ]
            elif folder_id is not None:
                cases = [c for c in cases if c.get("folder_id") == folder_id]
            elif root_only:
                cases = [c for c in cases if c.get("folder_id") is None]
            total = len(cases)
            total_pages = max(1, (total + per_page - 1) // per_page)
            start = (page - 1) * per_page
            end = start + per_page
            return _ok(
                {
                    "cases": cases[start:end],
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                }
            )

        if name == "cases.get":
            cid = int(args["case_id"])
            case = _ensure_case_visible(cid)
            if not case:
                return _err(f"Case {cid} not found", code="not_found")
            return _ok({"case": case})

        if name == "cases.create":
            payload = {
                "title": str(args["title"]).strip(),
                "jurisdiction": args.get("jurisdiction", "ke"),
                "legal_track": args.get("legal_track", "article_22_petition"),
                "description": (args.get("description") or "").strip(),
                "folder_id": args.get("folder_id"),
                "metadata": {
                    "owner_sub": user.sub,
                    "owner_name": user.name or user.sub,
                    "owner_email": user.email,
                    "created_via": "mcp",
                },
            }
            case = create_case(payload)
            if not case:
                return _err("Failed to create case")
            record_audit(
                actor="mcp",
                action="case_created",
                case_id=case["id"],
                resource=f"case={case['id']}",
                payload={"by": user.sub, "via": "mcp"},
            )
            return _ok({"case": case})

        if name == "cases.patch":
            cid = int(args["case_id"])
            case = _ensure_case_visible(cid)
            if not case:
                return _err(f"Case {cid} not found", code="not_found")
            from ..db import get_connection, utc_now

            fields: dict[str, str] = {}
            if "title" in args and args["title"] is not None:
                fields["title"] = str(args["title"]).strip()
                if not fields["title"]:
                    return _err("Title cannot be empty", code="bad_request")
            if "description" in args and args["description"] is not None:
                fields["description"] = str(args["description"]).strip()
            if not fields:
                return _ok({"case": case, "noop": True})
            now = utc_now()
            sql = f"UPDATE cases SET {', '.join(f'{k} = ?' for k in fields)}, updated_at = ? WHERE id = ?"
            with get_connection() as conn:
                conn.execute(sql, (*fields.values(), now, cid))
            record_audit(
                actor="mcp",
                action="case_patched",
                case_id=cid,
                resource=f"case={cid}",
                payload={"fields": list(fields.keys()), "by": user.sub},
            )
            return _ok({"case": get_case_full(cid)})

        if name == "cases.delete":
            cid = int(args["case_id"])
            case = _ensure_case_visible(cid)
            if not case:
                return _err(f"Case {cid} not found", code="not_found")
            from ..db import get_connection

            record_audit(
                actor="mcp",
                action="case_deleted",
                case_id=cid,
                resource=f"case={cid}",
                payload={"by": user.sub, "title": case.get("title")},
            )
            with get_connection() as conn:
                conn.execute("DELETE FROM cases WHERE id = ?", (cid,))
            return _ok({"ok": True, "case_id": cid})

        if name == "cases.move":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            target = args.get("folder_id")
            try:
                result = folder_service.move_case(cid, target)
            except ValueError as exc:
                return _err(str(exc), code="bad_request")
            if result is None:
                return _err(f"Case {cid} not found", code="not_found")
            record_audit(
                actor="mcp",
                action="case_moved",
                case_id=cid,
                resource=f"folder={target}",
                payload={"folder_id": target, "by": user.sub},
            )
            return _ok({"case_id": cid, "folder_id": target})

        if name == "cases.files":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            return _ok({"files": list_files(cid)})

        # ---- Folders ----
        if name == "folders.list":
            scope = None if has_global_case_scope(user) else user.sub
            return _ok({"folders": folder_service.list_folders(owner_sub=scope)})

        if name == "folders.create":
            try:
                folder = folder_service.create_folder(
                    name=str(args["name"]),
                    parent_id=args.get("parent_id"),
                    owner_sub=user.sub,
                )
            except ValueError as exc:
                return _err(str(exc), code="bad_request")
            record_audit(
                actor="mcp",
                action="folder_created",
                case_id=None,
                resource=f"folder={folder['id']}",
                payload={"by": user.sub, "name": folder["name"]},
            )
            return _ok({"folder": folder})

        if name == "folders.rename":
            try:
                folder = folder_service.rename_folder(
                    int(args["folder_id"]), str(args["name"])
                )
            except ValueError as exc:
                return _err(str(exc), code="bad_request")
            if not folder:
                return _err("Folder not found", code="not_found")
            return _ok({"folder": folder})

        if name == "folders.move":
            try:
                folder = folder_service.move_folder(
                    int(args["folder_id"]), args.get("parent_id")
                )
            except ValueError as exc:
                return _err(str(exc), code="bad_request")
            if not folder:
                return _err("Folder not found", code="not_found")
            return _ok({"folder": folder})

        if name == "folders.delete":
            ok = folder_service.delete_folder(int(args["folder_id"]))
            if not ok:
                return _err("Folder not found", code="not_found")
            return _ok({"ok": True, "folder_id": int(args["folder_id"])})

        # ---- Plan / generation ----
        if name == "plan.get":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            plan = load_plan(cid)
            if not plan:
                return _err("No plan saved for this case", code="not_found")
            return _ok({"plan": plan})

        if name == "plan.regenerate":
            cid = int(args["case_id"])
            case = _ensure_case_visible(cid)
            if case is None:
                return _err(f"Case {cid} not found", code="not_found")
            files = list_files_intake(cid)
            plan = propose_plan(case, files)
            save_plan(plan)
            return _ok({"plan": plan})

        if name == "plan.approve":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            plan = approve_plan(cid)
            if not plan:
                return _err("No plan to approve", code="not_found")
            return _ok({"plan": plan})

        if name == "generation.run":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            try:
                result = run_generation(cid)
            except ValueError as exc:
                return _err(str(exc), code="precondition_failed")
            return _ok(result)

        if name == "generation.runs":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            return _ok({"runs": list_runs(cid)})

        if name == "generation.events":
            return _ok({"events": list_events(int(args["run_id"]))})

        if name == "generation.latest":
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            run = latest_run(cid)
            if not run:
                return _err("No runs yet", code="not_found")
            return _ok({"run": run, "events": list_events(run["id"])})

        # ---- Outputs ----
        if name in {
            "outputs.bundle",
            "outputs.petition",
            "outputs.timeline",
            "outputs.precedents",
            "outputs.procedure",
        }:
            from ..config import GENERATED_DIR

            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            mapping = {
                "outputs.bundle": ("bundle.json", "json"),
                "outputs.petition": ("petition_draft.md", "text"),
                "outputs.timeline": ("evidence_codex.json", "json"),
                "outputs.precedents": ("precedent_linker.json", "json"),
                "outputs.procedure": ("procedural_engine.json", "json"),
            }
            filename, kind = mapping[name]
            path = GENERATED_DIR / f"case_{cid}" / filename
            if not path.exists():
                return _err(f"{filename} not generated yet", code="not_found")
            text = path.read_text(encoding="utf-8")
            if kind == "json":
                try:
                    return _ok(json.loads(text))
                except json.JSONDecodeError:
                    return _err(f"Could not parse {filename}", code="bad_state")
            return [TextContent(type="text", text=text)]

        # ---- Exports ----
        if name in {"exports.zip", "exports.encrypted", "exports.docker", "exports.usb"}:
            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            try:
                if name == "exports.zip":
                    from ..services.exporters import export_zip

                    path = export_zip(cid)
                elif name == "exports.encrypted":
                    from ..services.exporters import export_encrypted

                    passphrase = str(args.get("passphrase") or "")
                    if len(passphrase) < 8:
                        return _err(
                            "Passphrase must be ≥ 8 characters", code="bad_request"
                        )
                    path = export_encrypted(cid, passphrase=passphrase)
                elif name == "exports.docker":
                    from ..services.exporters import export_docker

                    path = export_docker(cid)
                else:
                    from ..services.exporters import export_usb

                    path = export_usb(cid)
            except FileNotFoundError as exc:
                return _err(str(exc), code="not_found")
            return _ok({"path": str(path), "exists": path.exists()})

        # ---- Audit ----
        if name == "audit.list":
            limit = max(1, min(1000, int(args.get("limit", 200))))
            return _ok(
                {"entries": list_audit(case_id=args.get("case_id"), limit=limit)}
            )

        # ---- MCP knowledge servers ----
        if name == "kenyalaw.search":
            from ..mcp import kenyalaw

            return _ok(
                {"results": kenyalaw.lookup_judgments(query=args.get("query"))}
            )

        if name == "kenyalaw.get":
            from ..mcp import kenyalaw

            judgment = kenyalaw.get_judgment(str(args["citation"]))
            return _ok({"judgment": judgment})

        if name == "case_knowledge.list":
            from ..mcp import case_knowledge

            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            return _ok({"evidence": case_knowledge.list_evidence(cid)})

        if name == "case_knowledge.text":
            from ..mcp import case_knowledge

            cid = int(args["case_id"])
            if _ensure_case_visible(cid) is None:
                return _err(f"Case {cid} not found", code="not_found")
            text = case_knowledge.get_evidence_text(cid, int(args["file_id"]))
            return [TextContent(type="text", text=text or "")]

        return _err(f"Unknown tool: {name}", code="unknown_tool")
    except Exception as exc:  # noqa: BLE001 — surface anything to the agent
        return _err(f"{type(exc).__name__}: {exc}", code="internal_error")


# ---------------------------------------------------------------------------
# Resources — read-only handles MCP clients can fetch by URI
# ---------------------------------------------------------------------------


def _resources() -> list[Resource]:
    return [
        Resource(
            uri="verda://docs/mcp",
            name="MCP integration guide",
            description="How AI agents and MCP-aware clients drive Verda end-to-end.",
            mimeType="text/markdown",
        ),
        Resource(
            uri="verda://schema/role-matrix",
            name="IAM role matrix",
            description="Static role → permission matrix Verda enforces on every API call.",
            mimeType="application/json",
        ),
    ]


def _read_resource(uri: str) -> str:
    if uri == "verda://docs/mcp":
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        doc = repo_root / "docs" / "MCP.md"
        if doc.exists():
            return doc.read_text(encoding="utf-8")
        return "MCP guide not found at docs/MCP.md"
    if uri == "verda://schema/role-matrix":
        from ..auth.permissions import list_role_matrix

        return json.dumps({"roles": list_role_matrix()}, indent=2)
    raise ValueError(f"Unknown resource URI: {uri}")


# ---------------------------------------------------------------------------
# Public server constructor
# ---------------------------------------------------------------------------


def build_server() -> Server:
    """Construct (but do not run) the MCP Server with every Verda tool wired."""
    initialize_db()
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:  # noqa: D401
        return _tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        return _dispatch(name, arguments or {})

    @server.list_resources()
    async def _list_resources() -> list[Resource]:
        return _resources()

    @server.read_resource()
    async def _read_resource_handler(uri: Any) -> str:
        return _read_resource(str(uri))

    return server


async def run_stdio() -> None:
    """Run the MCP server over stdio (the form Claude Desktop / Claude Code use)."""
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
