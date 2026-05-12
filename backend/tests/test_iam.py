"""IAM tests — role/permission matrix and per-case access.

These run against the in-process FastAPI app with auth flipped ON, so the
permission gates and case-access dependencies are exercised end-to-end.
"""
from __future__ import annotations

import datetime as dt
import os
import unittest
from contextlib import contextmanager
from unittest import mock

import jwt

from tests._helpers import isolated_runtime, seed_test_case


def _claims(sub: str, *roles: str, email: str = "test@wakili.local") -> dict:
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    return {
        "iss": "https://test-idp.local/realms/wakili",
        "aud": "wakili-frontend",
        "azp": "wakili-frontend",
        "sub": sub,
        "email": email,
        "name": sub,
        "iat": now,
        "exp": now + 600,
        "realm_access": {"roles": list(roles)},
    }


def _mint(claims: dict) -> str:
    return jwt.encode(claims, "irrelevant", algorithm="HS256")


@contextmanager
def _auth_on():
    prev = os.environ.get("WAKILI_AUTH_ENABLED")
    os.environ["WAKILI_AUTH_ENABLED"] = "true"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("WAKILI_AUTH_ENABLED", None)
        else:
            os.environ["WAKILI_AUTH_ENABLED"] = prev


class IAMTests(unittest.TestCase):
    """End-to-end IAM behaviour at the HTTP layer.

    Strategy: stub `verify_token` so the test mints any-shape JWT it needs
    (paralegal, lawyer, viewer, …) without standing up a real IdP. This
    asserts the permission + case-access wiring; cryptographic verification
    is exercised separately in test_auth.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from fastapi.testclient import TestClient

        from wakili.main import create_app

        cls.client = TestClient(create_app())

    @contextmanager
    def _as(self, sub: str, *roles: str):
        claims = _claims(sub, *roles)
        token = _mint(claims)
        with _auth_on(), mock.patch(
            "wakili.auth.dependencies.verify_token",
            side_effect=lambda t, **_: (
                claims if t == token else (_ for _ in ()).throw(Exception("nope"))
            ),
        ):
            yield {"Authorization": f"Bearer {token}"}

    def test_permissions_endpoint_returns_role_matrix(self):
        with self._as("u-1", "lawyer") as h:
            r = self.client.get("/api/auth/permissions", headers=h)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("permissions", body)
        self.assertIn("plan:approve", body["permissions"])
        roles = {entry["role"] for entry in body["role_matrix"]}
        for expected in ("lawyer", "paralegal", "admin", "auditor", "viewer"):
            self.assertIn(expected, roles)

    def test_paralegal_cannot_approve_plan(self):
        case_id = seed_test_case()["id"]
        with self._as("u-paralegal", "paralegal") as h:
            r = self.client.post(
                f"/api/cases/{case_id}/plan/approve", headers=h
            )
        # Paralegals lack `plan:approve`. The role-level gate trips first
        # (the case-access dep only runs after the permission dep when
        # both attach to the route).
        self.assertEqual(r.status_code, 403, msg=r.text)
        self.assertIn("plan:approve", r.json()["detail"])

    def test_viewer_cannot_write(self):
        case_id = seed_test_case()["id"]
        with self._as("u-viewer", "viewer") as h:
            r = self.client.patch(
                f"/api/cases/{case_id}",
                json={"description": "trying to edit"},
                headers=h,
            )
        # Viewer carries `cases:read` only; the write gate trips on the
        # role-level check.
        self.assertEqual(r.status_code, 403)
        self.assertIn("cases:write", r.json()["detail"])

    def test_non_member_sees_404_not_403(self):
        case_id = seed_test_case()["id"]
        # Create a lawyer who has all role-level perms but no ownership /
        # membership. Per-case access dep should respond 404 on read so
        # case ids can't be enumerated.
        with self._as("u-stranger", "lawyer") as h:
            r = self.client.get(f"/api/cases/{case_id}", headers=h)
        self.assertEqual(r.status_code, 404)

    def test_admin_has_global_scope(self):
        case_id = seed_test_case()["id"]
        with self._as("u-admin", "admin") as h:
            r = self.client.get(f"/api/cases/{case_id}", headers=h)
        self.assertEqual(r.status_code, 200, msg=r.text)
        access = r.json()["case"]["access"]
        self.assertEqual(access["via"], "global")

    def test_paralegal_blocked_from_encrypted_export(self):
        case_id = seed_test_case()["id"]
        # Approve plan + generate as a lawyer who owns nothing — admin has
        # global scope so this works without membership rows.
        with self._as("u-admin", "admin") as h:
            self.client.post(f"/api/cases/{case_id}/plan/approve", headers=h)
            self.client.post(f"/api/cases/{case_id}/generate", headers=h)

        with self._as("u-paralegal", "paralegal", "admin") as h:
            # paralegal+admin: admin grants global case scope so the case
            # access dep passes; encrypted export still gates on the
            # `exports:encrypted` permission, which paralegal does not have.
            # Drop "admin" so we test paralegal-only.
            pass

        # Now seed a case the paralegal owns so they pass case access, and
        # test that encrypted is still blocked.
        with self._as("u-para-owner", "paralegal") as h:
            created = self.client.post(
                "/api/cases",
                json={
                    "title": "Paralegal-owned",
                    "jurisdiction": "ke",
                    "legal_track": "article_22_petition",
                    "description": "x",
                },
                headers=h,
            )
            self.assertEqual(created.status_code, 201, msg=created.text)
            new_id = created.json()["case"]["id"]

            r = self.client.post(
                f"/api/cases/{new_id}/export",
                json={"target": "encrypted", "passphrase": "longenoughpassphrase"},
                headers=h,
            )
        self.assertEqual(r.status_code, 403)
        self.assertIn("exports:encrypted", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
