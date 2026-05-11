"""Entrypoint for ``python -m wakili.mcp_server``.

Speaks JSON-RPC 2.0 over stdio so MCP-aware clients (Claude Desktop,
Claude Code, mcp-cli, custom agents) can connect by spawning this
process. See ``docs/MCP.md`` for client configuration.
"""
from __future__ import annotations

import asyncio

from .server import run_stdio


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
