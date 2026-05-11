"""MCP-style internal services.

Per the technical architecture, Verda exposes its own MCP servers so generation
agents and the planner can call well-defined functions instead of scraping the
open web. Each call is recorded in the audit log.

The functions here are sync-callable for the in-process baseline. A real
deployment exposes them over the Model Context Protocol; the function shapes
are designed to map cleanly onto MCP tool definitions.
"""
