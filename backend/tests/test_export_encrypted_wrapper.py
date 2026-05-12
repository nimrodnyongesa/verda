"""Encrypted export wrapper — verifies the zip wrapper contents and
round-trips the bundled `decrypt.py` against the bundled `.wakili` blob."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests._helpers import cleanup_runtime, isolated_runtime, seed_test_case


class EncryptedWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from fastapi.testclient import TestClient

        from wakili.main import create_app

        cls.client = TestClient(create_app())
        cls.case_id = seed_test_case()["id"]
        cls.client.post(f"/api/cases/{cls.case_id}/plan/approve")
        cls.client.post(f"/api/cases/{cls.case_id}/generate")

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def test_zip_contains_blob_and_decrypter(self):
        from wakili.services.exporters.encrypted import export

        out = export(self.case_id, passphrase="bundle-passphrase-1234")
        self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        self.assertIn("decrypt.py", names)
        self.assertIn("README.md", names)
        self.assertTrue(any(n.endswith(".wakili") for n in names))

    def test_decrypt_py_round_trips_bundle(self):
        from wakili.services.exporters.encrypted import export

        passphrase = "decrypt-script-test-passphrase"
        out = export(self.case_id, passphrase=passphrase)

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with zipfile.ZipFile(out) as zf:
                zf.extractall(tmpdir)
            decrypter = tmpdir / "decrypt.py"
            blob = next(tmpdir.glob("*.wakili"))
            decoded = tmpdir / "decoded.zip"

            self.assertTrue(decrypter.exists())
            self.assertTrue(blob.exists())

            # Run the bundled decrypter as a subprocess. It must succeed using
            # only the standard library.
            result = subprocess.run(
                [sys.executable, str(decrypter), str(blob), passphrase, str(decoded)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=f"decrypt.py failed: stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            self.assertTrue(decoded.exists())

            # The decoded payload should be a zip containing bundle.json.
            with zipfile.ZipFile(decoded) as inner:
                self.assertIn("bundle.json", inner.namelist())

    def test_decrypt_py_rejects_wrong_passphrase(self):
        from wakili.services.exporters.encrypted import export

        out = export(self.case_id, passphrase="real-passphrase-aaaa")
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with zipfile.ZipFile(out) as zf:
                zf.extractall(tmpdir)
            decrypter = tmpdir / "decrypt.py"
            blob = next(tmpdir.glob("*.wakili"))

            result = subprocess.run(
                [sys.executable, str(decrypter), str(blob), "WRONG", str(tmpdir / "x.zip")],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
