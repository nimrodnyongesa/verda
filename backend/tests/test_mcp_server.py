"""MCP server tests — tool catalog + key dispatch paths.

Calls _dispatch directly so the test stays in-process (no JSON-RPC
transport). The HTTP route path and the MCP path share the same service
layer, so these tests focus on the MCP-specific glue: tool catalog,
auth-shim handling, and error envelope shape.
"""
from __future__ import annotations

import json
import unittest

from tests._helpers import isolated_runtime, seed_test_case


class McpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from wakili.mcp_server.server import build_server, _dispatch, _tools

        cls.build_server = staticmethod(build_server)
        cls.dispatch = staticmethod(_dispatch)
        cls.tools = staticmethod(_tools)

    def _payload(self, name: str, args: dict | None = None) -> dict:
        result = self.dispatch(name, args or {})
        self.assertEqual(len(result), 1)
        return json.loads(result[0].text)

    def test_server_name_and_tool_catalog(self):
        server = self.build_server()
        self.assertEqual(server.name, "verda")
        names = [t.name for t in self.tools()]
        # Sanity: every namespace is present.
        for prefix in (
            "cases.",
            "folders.",
            "plan.",
            "generation.",
            "outputs.",
            "exports.",
            "audit.",
            "kenyalaw.",
            "case_knowledge.",
            "iam.",
        ):
            self.assertTrue(
                any(n.startswith(prefix) for n in names),
                msg=f"No tool namespaced under {prefix!r}",
            )
        # Each tool must declare an inputSchema.
        for tool in self.tools():
            self.assertIsNotNone(tool.inputSchema)
            self.assertEqual(tool.inputSchema.get("type"), "object")

    def test_unknown_tool_returns_error_envelope(self):
        body = self._payload("does.not.exist", {})
        self.assertEqual(body["error"], "unknown_tool")

    def test_iam_whoami_shape(self):
        body = self._payload("iam.whoami", {})
        for key in ("sub", "roles", "permissions", "global_case_scope", "anonymous"):
            self.assertIn(key, body)

    def test_iam_role_matrix(self):
        body = self._payload("iam.role_matrix", {})
        roles = {r["role"] for r in body["roles"]}
        self.assertGreaterEqual(roles, {"admin", "lawyer", "paralegal", "viewer", "auditor"})

    def test_cases_list_pagination(self):
        # Seed two cases so pagination has something to work with.
        for _ in range(3):
            seed_test_case(title=f"MCP seed {_}")
        body = self._payload("cases.list", {"page": 1, "per_page": 2})
        self.assertIn("total", body)
        self.assertIn("total_pages", body)
        self.assertEqual(body["per_page"], 2)
        self.assertLessEqual(len(body["cases"]), 2)

    def test_cases_get_unknown_returns_not_found(self):
        body = self._payload("cases.get", {"case_id": 999_999})
        self.assertEqual(body["error"], "not_found")

    def test_folder_lifecycle_via_mcp(self):
        # Create → list → rename → move-case → delete.
        folder = self._payload("folders.create", {"name": "MCP folder"})["folder"]
        self.assertEqual(folder["name"], "MCP folder")

        listed = self._payload("folders.list", {})["folders"]
        self.assertTrue(any(f["id"] == folder["id"] for f in listed))

        renamed = self._payload(
            "folders.rename", {"folder_id": folder["id"], "name": "MCP archive"}
        )["folder"]
        self.assertEqual(renamed["name"], "MCP archive")

        case_id = seed_test_case(title="Folder-bound MCP")["id"]
        self._payload(
            "cases.move", {"case_id": case_id, "folder_id": folder["id"]}
        )
        case = self._payload("cases.get", {"case_id": case_id})["case"]
        self.assertEqual(case["folder_id"], folder["id"])

        out = self._payload("folders.delete", {"folder_id": folder["id"]})
        self.assertTrue(out["ok"])

        # Case fell back to root.
        case = self._payload("cases.get", {"case_id": case_id})["case"]
        self.assertIsNone(case["folder_id"])


if __name__ == "__main__":
    unittest.main()
