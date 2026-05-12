"""Auth dependency tests.

Covers:
  - Anonymous mode (WAKILI_AUTH_ENABLED unset → routes pass through).
  - Auth enforced + missing token → 401.
  - Auth enforced + verifiable token → 200 with claims.

We don't talk to a real IdP; instead we generate an RSA keypair, mint a
token, and patch the OIDC layer to accept that key.
"""
from __future__ import annotations

import datetime as dt
import os
import unittest
from unittest import mock

from tests._helpers import isolated_runtime


def _make_jwt(claims: dict) -> str:
    """Mint a non-cryptographic JWT for the dependency test.

    Production verification (signature, JWKS) is exercised by
    ``wakili.auth.oidc.verify_token`` and patched in this test — the goal
    here is to assert that a successfully-verified token correctly threads
    the user object into the FastAPI dependency.
    """
    import jwt
    return jwt.encode(claims, "irrelevant", algorithm="HS256")


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        isolated_runtime()
        from fastapi.testclient import TestClient

        from wakili.main import create_app

        cls.client = TestClient(create_app())

    def setUp(self):
        # Auth is ON by default in production. Tests in this class flip it
        # explicitly per case; reset to the test-safe default before each.
        os.environ["WAKILI_AUTH_ENABLED"] = "false"

    def tearDown(self):
        os.environ["WAKILI_AUTH_ENABLED"] = "false"

    def test_anonymous_mode_passes_through(self):
        r = self.client.post(
            "/api/cases",
            json={
                "title": "Anon-mode smoke",
                "jurisdiction": "ke",
                "legal_track": "article_22_petition",
                "description": "x",
                "metadata": {},
            },
        )
        self.assertEqual(r.status_code, 201)

    def test_whoami_anonymous(self):
        r = self.client.get("/api/auth/whoami")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["anonymous"])

    def test_providers_endpoint_lists_keycloak(self):
        from wakili.auth.providers import reset_cache
        reset_cache()
        r = self.client.get("/api/auth/providers")
        self.assertEqual(r.status_code, 200)
        ids = [p["id"] for p in r.json()["providers"]]
        self.assertIn("keycloak", ids)

    def test_auth_required_rejects_missing_token(self):
        os.environ["WAKILI_AUTH_ENABLED"] = "true"
        try:
            r = self.client.get("/api/cases")
            self.assertEqual(r.status_code, 401)
            self.assertIn("Bearer", r.headers.get("www-authenticate", ""))
        finally:
            os.environ["WAKILI_AUTH_ENABLED"] = "false"

    def test_auth_required_rejects_invalid_token(self):
        os.environ["WAKILI_AUTH_ENABLED"] = "true"
        try:
            r = self.client.get(
                "/api/cases",
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
            self.assertEqual(r.status_code, 401)
        finally:
            os.environ["WAKILI_AUTH_ENABLED"] = "false"

    def test_auth_required_accepts_verified_token(self):
        from wakili.auth import dependencies as deps

        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        claims = {
            "iss": "https://test-idp.local/realms/wakili",
            "aud": "wakili-frontend",
            "azp": "wakili-frontend",
            "sub": "user-123",
            "email": "advocate@wakili.local",
            "name": "Demo Advocate",
            "iat": now,
            "exp": now + 600,
            "realm_access": {"roles": ["lawyer"]},
        }
        token = _make_jwt(claims)

        os.environ["WAKILI_AUTH_ENABLED"] = "true"
        # Bypass JWKS fetch + signature verification: stub verify_token to just
        # return the claims when the same token is presented. Production code
        # path verifies signatures; this test asserts the dependency wiring.
        with mock.patch(
            "wakili.auth.dependencies.verify_token",
            side_effect=lambda t, **_: (
                claims if t == token else (_ for _ in ()).throw(Exception("nope"))
            ),
        ):
            r = self.client.get(
                "/api/cases",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(r.status_code, 200, msg=r.text)

            r = self.client.get(
                "/api/auth/whoami",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["sub"], "user-123")
            self.assertIn("lawyer", body["roles"])
            self.assertFalse(body["anonymous"])
        os.environ["WAKILI_AUTH_ENABLED"] = "false"
        deps.ANON  # no-op


if __name__ == "__main__":
    unittest.main()
