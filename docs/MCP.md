# Verda — MCP server

Verda ships a first-class **Model Context Protocol** server so an LLM
agent can drive the platform end-to-end without the operator hand-rolling
HTTP shims. Every domain operation the FastAPI surface offers (cases,
folders, plans, generation, exports, audit, evidence reads, IAM
introspection) is exposed as an MCP tool with a typed JSON Schema.

If you've never seen MCP: it's an open standard from Anthropic for how
LLMs talk to external tools and resources. The wire format is JSON-RPC
2.0 over stdio. Claude Desktop, Claude Code, the `mcp-cli`, and any
SDK-based agent (Anthropic, OpenAI, local) can speak it.

## Quick start (Claude Desktop)

Add this block to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "verda": {
      "command": "/abs/path/to/wakili/.venv/bin/python",
      "args": ["-m", "wakili.mcp_server"],
      "env": {
        "PYTHONPATH": "/abs/path/to/wakili/backend",
        "WAKILI_RUNTIME_DIR": "/abs/path/to/wakili/runtime",
        "WAKILI_AUTH_ENABLED": "false",
        "VERDA_MCP_USER_SUB": "nimrod",
        "VERDA_MCP_USER_ROLES": "lawyer,admin"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see a **🔌 verda** indicator in the
composer; the model can now call any Verda tool by name.

## Quick start (Claude Code)

```bash
claude mcp add verda -- /abs/path/.venv/bin/python -m wakili.mcp_server
```

Then in any Claude Code session:

```
/mcp
> verda · 31 tools loaded
```

## Quick start (mcp-cli, ad-hoc agents)

```bash
PYTHONPATH=backend WAKILI_AUTH_ENABLED=false \
  .venv/bin/python -m wakili.mcp_server
```

The process speaks JSON-RPC 2.0 on stdin/stdout. Any client that can
spawn a subprocess and pipe JSON-RPC frames to it can drive Verda.

## Authentication model

The MCP server runs **in-process** with the same auth flag the HTTP API
respects (`WAKILI_AUTH_ENABLED`). Two modes:

| `WAKILI_AUTH_ENABLED` | Behaviour |
| --- | --- |
| `false` (or unset) | Synthetic anonymous user. Every tool succeeds. Local-only / CI / dev. |
| `true` + `VERDA_MCP_USER_SUB` set | The MCP session acts as that user. Their realm roles drive permissions and per-case scope. |
| `true` + no `VERDA_MCP_USER_SUB` | Synthetic anonymous (which carries every permission) — convenient for trusted local agents. |

The MCP transport is stdio, which means the operator who launches the
server has already crossed the trust boundary at the OS level. The IAM
layer still applies: the synthetic user's roles control which cases the
agent can read, which exports it can build, etc. There is no per-tool
bypass.

Optional environment variables:

```bash
VERDA_MCP_USER_SUB=nimrod          # who the agent acts as
VERDA_MCP_USER_ROLES=lawyer,admin   # comma-separated realm roles
VERDA_MCP_USER_NAME="Nimrod Admin"
VERDA_MCP_USER_EMAIL="nimrod@wakili.local"
```

## Tool catalog

31 tools across 9 namespaces. Every tool returns one or more
`text/content` parts containing JSON; failures surface as
`{"error": "<code>", "message": "<…>"}` payloads instead of throwing,
so the agent can reason about them.

### `cases.*` — case CRUD + read

| Tool | Args | Returns |
| --- | --- | --- |
| `cases.list` | `page?`, `per_page?`, `q?`, `folder_id?`, `root_only?` | Paginated `cases[]` + `total`, `page`, `per_page`, `total_pages`. |
| `cases.get` | `case_id` | Full case record (files, plan, latest run). |
| `cases.create` | `title`, `jurisdiction?`, `legal_track?`, `description?`, `folder_id?` | Created case. |
| `cases.patch` | `case_id`, `title?`, `description?` | Updated case. |
| `cases.delete` | `case_id` | `{ok, case_id}` (hard delete). |
| `cases.move` | `case_id`, `folder_id` | `{case_id, folder_id}`. |
| `cases.files` | `case_id` | Evidence file list (no extracted text). |

### `folders.*` — owner-scoped + admin-global hierarchy

| Tool | Args |
| --- | --- |
| `folders.list` | — |
| `folders.create` | `name`, `parent_id?` |
| `folders.rename` | `folder_id`, `name` |
| `folders.move` | `folder_id`, `parent_id?` (cycle-safe) |
| `folders.delete` | `folder_id` (children cascade, cases fall to root) |

### `plan.*` & `generation.*` — toolkit pipeline

| Tool | Notes |
| --- | --- |
| `plan.get` | Returns the saved plan or `not_found`. |
| `plan.regenerate` | Re-runs the planner against current evidence. |
| `plan.approve` | Lawyer-in-the-loop gate. Required before generation. |
| `generation.run` | Executes the deterministic generator. Plan must be approved or returns `precondition_failed`. |
| `generation.runs` | History for a case. |
| `generation.events` | Codex-replay event stream for a run id. |
| `generation.latest` | Latest run + its events for a case. |

### `outputs.*` — read-only artifact handles

| Tool | Returns |
| --- | --- |
| `outputs.bundle` | Final `bundle.json`. |
| `outputs.petition` | Drafted petition markdown. |
| `outputs.timeline` | Evidence Codex JSON. |
| `outputs.precedents` | Precedent Linker JSON. |
| `outputs.procedure` | Procedural Engine JSON. |

### `exports.*` — produce real, runnable artifacts

| Tool | Args | Returns |
| --- | --- | --- |
| `exports.zip` | `case_id` | `{path}` (flat zip on disk). |
| `exports.encrypted` | `case_id`, `passphrase` (≥ 8 chars) | AES-256-GCM bundle + stdlib decrypter. |
| `exports.docker` | `case_id` | `{path}` to a self-hosted Docker viewer tarball. |
| `exports.usb` | `case_id` | `{path}` to a USB-portable viewer zip. |

### `audit.*`

| Tool | Args |
| --- | --- |
| `audit.list` | `case_id?`, `limit?` (default 200, max 1000) |

### `kenyalaw.*` & `case_knowledge.*`

| Tool | Purpose |
| --- | --- |
| `kenyalaw.search` | Query the bundled real Kenya Law judgment corpus. Every URL is a verified `kenyalaw.org` URL. |
| `kenyalaw.get` | Fetch one judgment by citation. |
| `case_knowledge.list` | Per-case evidence index. |
| `case_knowledge.text` | Extracted full text of one evidence file. |

### `iam.*` — introspection

| Tool | Returns |
| --- | --- |
| `iam.whoami` | sub, roles, effective permissions, global-case-scope, anonymous flag. |
| `iam.role_matrix` | Full role → permission matrix (UI consumes the same shape). |

## Resources

Two MCP resources are exposed:

| URI | MIME | Body |
| --- | --- | --- |
| `verda://docs/mcp` | `text/markdown` | This file. |
| `verda://schema/role-matrix` | `application/json` | Role/permission matrix. |

A client can list and read these without invoking a tool — useful for
giving the agent system-level context up front.

## Example agent flow — "Move all stale Article 22 cases to an archive folder"

```text
1. iam.whoami                                       → confirm role + permissions
2. folders.list                                     → discover existing folders
3. folders.create  { name: "Archive · 2024", parent_id: null }
4. cases.list      { q: "article_22", per_page: 100 }
5. for each case where status == "filed" and updated_at < cutoff:
     cases.move    { case_id: …, folder_id: <archive id> }
6. audit.list      { case_id: null, limit: 50 }     → confirm the moves landed
```

Each step returns structured JSON, so the agent can branch on errors
(`not_found`, `precondition_failed`, `bad_request`) without parsing
free-form prose.

## Example agent flow — "Generate and ship an encrypted bundle"

```text
1. cases.get          { case_id: 42 }
2. plan.get           { case_id: 42 }
   if missing → plan.regenerate { case_id: 42 }
3. plan.approve       { case_id: 42 }
4. generation.run     { case_id: 42 }
5. outputs.bundle     { case_id: 42 }     → quick sanity check on counts
6. exports.encrypted  { case_id: 42, passphrase: "<from env>" }
7. cases.move         { case_id: 42, folder_id: <"Filed" folder> }
```

`exports.encrypted` returns the absolute path on disk; the agent (or
the host process that spawned the agent) can then deliver the file
through whatever channel makes sense (object storage, secure share,
etc.) — Verda itself has no outbound network calls.

## Failure semantics

Every tool returns one of three outcomes:

1. **Success** — JSON payload (per-tool shape, see catalog).
2. **Domain failure** — `{"error": "<code>", "message": "<…>"}`. Codes:
   `not_found`, `bad_request`, `precondition_failed`, `unknown_tool`,
   `bad_state`.
3. **Internal exception** — `{"error": "internal_error", "message":
   "<TypeName>: <message>"}`. The agent should treat this as
   non-retryable without operator inspection.

Tools never raise to the MCP transport. The agent always receives a
parseable response, so it can plan and recover.

## Adding a new tool

1. Add a `Tool(...)` entry to `_tools()` in
   `backend/wakili/mcp_server/server.py` with a precise `inputSchema`.
2. Handle the tool name in `_dispatch(...)`. Keep the function pure —
   call into `services/` or `auth/` modules, return `_ok(...)` /
   `_err(...)`.
3. Update this document and add a row to the catalog table above.
4. Write a unit test under `backend/tests/test_mcp_server.py`.

## Smoke-test the server (without an LLM)

```bash
PYTHONPATH=backend .venv/bin/python -c "
import asyncio, json
from wakili.mcp_server.server import build_server

server = build_server()
async def main():
    tools = await server.request_handlers[type(__import__('mcp').types.ListToolsRequest)](
        __import__('mcp').types.ListToolsRequest(method='tools/list')
    )
    print(json.dumps([t.model_dump() for t in tools.root.tools][:3], indent=2))
asyncio.run(main())
"
```

For a fuller protocol-level test, install `mcp-cli`:

```bash
.venv/bin/pip install 'mcp[cli]'
mcp dev backend/wakili/mcp_server/__main__.py
```

The dev inspector runs both halves of the conversation in your browser
and validates every tool's input/output schema.

## What's next

- Streaming long-running tool calls (`generation.run` currently returns
  the final summary; the per-event stream is reachable via
  `generation.events` after-the-fact).
- HTTP-streaming MCP transport (the spec's other supported transport)
  so multi-tenant deployments can multiplex the server.
- Per-tool rate limits driven by the IAM permission set.

Open a PR with the change and a test in `backend/tests/test_mcp_server.py`.
