"""Docker export — verifies tar contents; if `docker` CLI is available,
runs `docker build` to confirm the artifact is buildable."""
from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from tests._helpers import cleanup_runtime, isolated_runtime, seed_test_case


class DockerExportTests(unittest.TestCase):
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

    def _expected_files(self, members: list[str]) -> None:
        # Every artifact lives under a single top-level dir inside the tarball.
        flat = {m.split("/", 1)[1] if "/" in m else m for m in members}
        for name in (
            "Dockerfile",
            "requirements.txt",
            "docker-compose.yml",
            "README.md",
            "wakili_case_server/main.py",
            "templates/base.html",
            "templates/index.html",
            "templates/timeline.html",
            "templates/petition.html",
            "templates/precedents.html",
            "templates/procedure.html",
            "static/styles.css",
            "case_data/bundle.json",
            "case_data/petition_draft.md",
        ):
            self.assertIn(name, flat, msg=f"{name} missing from tarball")

    def test_tarball_contains_expected_files(self):
        from wakili.services.exporters.docker import export

        out = export(self.case_id)
        self.assertTrue(out.exists())
        with tarfile.open(out, "r:gz") as tar:
            members = tar.getnames()
        self._expected_files(members)

    def test_docker_build_works_if_docker_available(self):
        if shutil.which("docker") is None:
            self.skipTest("docker CLI not installed")
        # Probe that the daemon is actually reachable; otherwise skip.
        probe = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if probe.returncode != 0:
            self.skipTest(f"docker daemon unreachable: {probe.stderr.strip()[:120]}")

        from wakili.services.exporters.docker import export

        out = export(self.case_id)

        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(out, "r:gz") as tar:
                tar.extractall(tmp)
            top = next(p for p in Path(tmp).iterdir() if p.is_dir())
            tag = f"wakili-test-case-{self.case_id}:test"
            try:
                build = subprocess.run(
                    ["docker", "build", "-t", tag, str(top)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.assertEqual(
                    build.returncode,
                    0,
                    msg=f"docker build failed:\nstdout={build.stdout[-1000:]}\nstderr={build.stderr[-1000:]}",
                )
            finally:
                subprocess.run(["docker", "rmi", "-f", tag], capture_output=True, timeout=60)

    def test_standalone_server_serves_views(self):
        """The mini FastAPI app inside the tarball must boot in a subprocess.

        Skip if FastAPI/uvicorn aren't importable in this environment.
        """
        try:
            import fastapi  # noqa: F401
            import uvicorn  # noqa: F401
        except Exception:
            self.skipTest("fastapi/uvicorn not importable")

        import socket
        import sys
        import time
        import urllib.request

        from wakili.services.exporters.docker import export

        out = export(self.case_id)
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(out, "r:gz") as tar:
                tar.extractall(tmp)
            top = next(p for p in Path(tmp).iterdir() if p.is_dir())

            # Pick a free port.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]

            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "wakili_case_server.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=str(top),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                # Wait for boot.
                deadline = time.time() + 20.0
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/healthz", timeout=1
                        ) as r:
                            if r.status == 200:
                                break
                    except Exception:
                        time.sleep(0.25)
                else:
                    out_b, err_b = proc.communicate(timeout=5)
                    self.fail(
                        f"server did not become ready on port {port}: stdout={out_b!r} stderr={err_b!r}"
                    )

                for path in ("/", "/timeline", "/petition", "/precedents", "/procedure"):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{path}", timeout=5
                    ) as r:
                        self.assertEqual(r.status, 200, msg=f"{path}")
                        body = r.read().decode("utf-8", errors="replace")
                        self.assertGreater(len(body), 100)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    unittest.main()
