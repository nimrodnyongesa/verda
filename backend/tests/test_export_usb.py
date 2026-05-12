"""USB export — verifies MANIFEST.json hashes, then boots wakili-launcher.py
in a subprocess and hits viewer.html."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path

from tests._helpers import cleanup_runtime, isolated_runtime, seed_test_case


class UsbExportTests(unittest.TestCase):
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

    def test_zip_contents_and_manifest(self):
        from wakili.services.exporters.usb import export

        out = export(self.case_id)
        self.assertTrue(out.exists())

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with zipfile.ZipFile(out) as zf:
                zf.extractall(tmpdir)

            top = next(p for p in tmpdir.iterdir() if p.is_dir())
            for name in (
                "viewer.html",
                "wakili-launcher.py",
                "RUN.sh",
                "RUN.bat",
                "MANIFEST.json",
                "INSTALL_TAILS.md",
                "verify.sh",
                "case_data/bundle.json",
                "case_data/petition_draft.md",
            ):
                self.assertTrue((top / name).exists(), msg=f"{name} missing")

            # MANIFEST.json hashes must match every file's actual sha256.
            manifest = json.loads((top / "MANIFEST.json").read_text())
            for rel, expected in manifest["files"].items():
                actual = hashlib.sha256((top / rel).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, msg=f"hash mismatch for {rel}")

    def test_launcher_serves_viewer_with_case_title(self):
        from wakili.services.exporters.usb import export

        out = export(self.case_id)
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with zipfile.ZipFile(out) as zf:
                zf.extractall(tmpdir)
            top = next(p for p in tmpdir.iterdir() if p.is_dir())

            launcher = top / "wakili-launcher.py"
            self.assertTrue(launcher.exists())

            proc = subprocess.Popen(
                [sys.executable, str(launcher), "--no-browser"],
                cwd=str(top),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                # Read the launcher's announced URL from stderr/stdout (it
                # prints "Verda viewer at http://127.0.0.1:PORT/viewer.html").
                port = None
                deadline = time.time() + 10.0
                while time.time() < deadline and port is None:
                    line = proc.stdout.readline().decode("utf-8", errors="replace")
                    if "viewer at" in line:
                        # parse "...127.0.0.1:NNNN/viewer.html"
                        for tok in line.split():
                            if "127.0.0.1:" in tok:
                                port = int(tok.split(":")[2].split("/")[0])
                                break
                self.assertIsNotNone(port, msg="launcher did not announce a URL")

                # Hit /viewer.html and assert HTML response containing case title.
                bundle = json.loads((top / "case_data" / "bundle.json").read_text())
                title = bundle["case_summary"]["title"]

                # Wait for server to be ready
                ready = False
                deadline = time.time() + 5.0
                while time.time() < deadline and not ready:
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/viewer.html", timeout=1
                        ) as r:
                            html = r.read().decode("utf-8", errors="replace")
                            self.assertEqual(r.status, 200)
                            self.assertIn("Verda", html)
                            # Title is loaded by JS at runtime; the doc itself
                            # must reference the case_data path it fetches.
                            self.assertIn("case_data/bundle.json", html)
                            ready = True
                    except Exception:
                        time.sleep(0.2)
                self.assertTrue(ready, "viewer.html not reachable")

                # Also confirm bundle.json itself is served at the right path.
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/case_data/bundle.json", timeout=2
                ) as r:
                    payload = json.loads(r.read())
                    self.assertEqual(payload["case_summary"]["title"], title)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    unittest.main()
