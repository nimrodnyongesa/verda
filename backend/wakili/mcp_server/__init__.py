"""Verda MCP server — Model Context Protocol surface for AI agents.

Exposes the same domain operations the FastAPI surface offers (cases,
folders, plans, generation, exports, audit, evidence reads) as MCP tools
+ resources, so any MCP-aware client (Claude Desktop, Claude Code,
``mcp-cli``, custom agents) can drive Verda directly.

Run with::

    PYTHONPATH=backend python -m wakili.mcp_server

See ``docs/MCP.md`` for the integration walkthrough.
"""

from .server import build_server, run_stdio  # noqa: F401

__all__ = ["build_server", "run_stdio"]
