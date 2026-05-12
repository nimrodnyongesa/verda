"""Folder API tests — covers create, nest, rename, move, delete + case move.

Runs in anonymous mode so the IAM role gates pass; the folder service
itself enforces ownership / cycle / cascade rules independently.
"""
from __future__ import annotations

import unittest

from tests._helpers import isolated_runtime, seed_test_case


class FoldersApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from fastapi.testclient import TestClient

        from wakili.main import create_app

        cls.client = TestClient(create_app())

    def _create(self, name: str, parent_id: int | None = None) -> int:
        body: dict = {"name": name}
        if parent_id is not None:
            body["parent_id"] = parent_id
        r = self.client.post("/api/folders", json=body)
        self.assertEqual(r.status_code, 201, msg=r.text)
        return r.json()["folder"]["id"]

    def test_root_folder_round_trip(self):
        before = self.client.get("/api/folders").json()["folders"]
        fid = self._create("Detentions · 2024")
        after = self.client.get("/api/folders").json()["folders"]
        self.assertEqual(len(after), len(before) + 1)
        self.assertTrue(any(f["id"] == fid and f["name"] == "Detentions · 2024" for f in after))

    def test_nest_and_rename(self):
        parent = self._create("Strategic litigation")
        child = self._create("Article 22 petitions", parent_id=parent)

        # Rename
        r = self.client.patch(f"/api/folders/{child}", json={"name": "Article 22"})
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertEqual(r.json()["folder"]["name"], "Article 22")

        # Empty rename rejected
        r = self.client.patch(f"/api/folders/{child}", json={"name": "  "})
        self.assertEqual(r.status_code, 400)

    def test_move_folder_rejects_cycle(self):
        a = self._create("A")
        b = self._create("B", parent_id=a)
        c = self._create("C", parent_id=b)

        # Cannot move A under C (its descendant)
        r = self.client.post(f"/api/folders/{a}/move", json={"parent_id": c})
        self.assertEqual(r.status_code, 400)
        self.assertIn("descendant", r.json()["detail"])

        # Move B back to root
        r = self.client.post(f"/api/folders/{b}/move", json={"parent_id": None})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["folder"]["parent_id"])

    def test_delete_cascades_children_and_releases_cases(self):
        case_id = seed_test_case(title="Folder-test seed")["id"]
        parent = self._create("Parent box")
        child = self._create("Child box", parent_id=parent)

        # Move case into child
        r = self.client.post(f"/api/cases/{case_id}/move", json={"folder_id": child})
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertEqual(r.json()["folder_id"], child)

        # Delete parent — child cascades, case returns to root.
        r = self.client.delete(f"/api/folders/{parent}")
        self.assertEqual(r.status_code, 200)

        listing = self.client.get("/api/folders").json()["folders"]
        self.assertFalse(any(f["id"] in (parent, child) for f in listing))

        case = self.client.get(f"/api/cases/{case_id}").json()["case"]
        self.assertIsNone(case.get("folder_id"))

    def test_move_case_unknown_folder_404(self):
        case_id = seed_test_case(title="Move-target seed")["id"]
        r = self.client.post(f"/api/cases/{case_id}/move", json={"folder_id": 99_999})
        self.assertEqual(r.status_code, 404)

    def test_move_case_to_root(self):
        case_id = seed_test_case(title="Root-bound seed")["id"]
        fid = self._create("Holding pen")
        self.client.post(f"/api/cases/{case_id}/move", json={"folder_id": fid})
        r = self.client.post(f"/api/cases/{case_id}/move", json={"folder_id": None})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["folder_id"])


if __name__ == "__main__":
    unittest.main()
