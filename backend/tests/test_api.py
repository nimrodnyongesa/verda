"""HTTP-level smoke test using FastAPI's TestClient."""
import unittest

from tests._helpers import cleanup_runtime, isolated_runtime, seed_test_case


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from fastapi.testclient import TestClient

        from wakili.main import create_app

        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def _seed(self) -> int:
        """Seed a sample case at the service layer, return its id.

        Tests that need a populated case use this instead of an HTTP demo
        endpoint — the demo endpoint was removed when the IAM layer landed.
        """
        return seed_test_case()["id"]

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("llm", body)

    def test_patch_case_renames_title(self):
        case_id = self._seed()
        # Rename
        r = self.client.patch(
            f"/api/cases/{case_id}",
            json={"title": "Petition for Six Detained Protesters · 5/5/2026"},
        )
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertEqual(
            r.json()["case"]["title"],
            "Petition for Six Detained Protesters · 5/5/2026",
        )
        # Empty title rejected
        r = self.client.patch(f"/api/cases/{case_id}", json={"title": "   "})
        self.assertEqual(r.status_code, 400)
        # Description-only update preserves title
        r = self.client.patch(
            f"/api/cases/{case_id}", json={"description": "Updated facts."}
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()["case"]
        self.assertEqual(body["description"], "Updated facts.")
        self.assertEqual(
            body["title"],
            "Petition for Six Detained Protesters · 5/5/2026",
        )
        # Unknown case → 404
        r = self.client.patch("/api/cases/999999", json={"title": "x"})
        self.assertEqual(r.status_code, 404)

    def test_seed_then_generate_full_flow(self):
        case_id = self._seed()
        # Approve plan and run generation.
        r = self.client.post(f"/api/cases/{case_id}/plan/approve")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"/api/cases/{case_id}/generate")
        self.assertEqual(r.status_code, 200)

        # Outputs.
        for path in (
            f"/api/cases/{case_id}/timeline",
            f"/api/cases/{case_id}/precedents",
            f"/api/cases/{case_id}/procedure",
            f"/api/cases/{case_id}/petition",
            f"/api/cases/{case_id}/runs/latest",
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, msg=f"{path} -> {r.status_code}")

    def test_export_zip_round_trip(self):
        case_id = self._seed()
        self.client.post(f"/api/cases/{case_id}/plan/approve")
        self.client.post(f"/api/cases/{case_id}/generate")

        r = self.client.post(
            f"/api/cases/{case_id}/export", json={"target": "zip"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/zip", r.headers.get("content-type", ""))
        self.assertGreater(len(r.content), 1000)

    def test_export_encrypted_round_trip(self):
        from wakili.services.encryption import decrypt
        import zipfile
        from io import BytesIO

        case_id = self._seed()
        self.client.post(f"/api/cases/{case_id}/plan/approve")
        self.client.post(f"/api/cases/{case_id}/generate")

        passphrase = "this-is-a-strong-passphrase"
        r = self.client.post(
            f"/api/cases/{case_id}/export",
            json={"target": "encrypted", "passphrase": passphrase},
        )
        self.assertEqual(r.status_code, 200)
        # Encrypted target now returns a zip wrapper containing the encrypted
        # blob + a stand-alone decrypter + a README.
        with zipfile.ZipFile(BytesIO(r.content)) as wrapper:
            names = wrapper.namelist()
            blob_name = next(n for n in names if n.endswith(".wakili"))
            self.assertIn("decrypt.py", names)
            self.assertIn("README.md", names)
            blob = wrapper.read(blob_name)
        self.assertTrue(blob.startswith(b"WAKILI1"))
        decrypted = decrypt(blob, passphrase)
        with zipfile.ZipFile(BytesIO(decrypted)) as zf:
            self.assertIn("bundle.json", zf.namelist())

    def test_export_encrypted_requires_strong_passphrase(self):
        case_id = self._seed()
        self.client.post(f"/api/cases/{case_id}/plan/approve")
        self.client.post(f"/api/cases/{case_id}/generate")
        r = self.client.post(
            f"/api/cases/{case_id}/export",
            json={"target": "encrypted", "passphrase": "short"},
        )
        self.assertEqual(r.status_code, 400)

    def test_audit_log_records_events(self):
        case_id = self._seed()
        # Touch the case so audit picks up at least one entry.
        self.client.patch(f"/api/cases/{case_id}", json={"description": "ping"})
        r = self.client.get(f"/api/audit?case_id={case_id}")
        self.assertEqual(r.status_code, 200)
        entries = r.json()["entries"]
        self.assertGreater(len(entries), 0)


if __name__ == "__main__":
    unittest.main()
