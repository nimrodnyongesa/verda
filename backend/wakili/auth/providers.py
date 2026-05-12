"""OIDC provider registry.

Every provider follows the same shape: an issuer URL Verda can fetch a
``.well-known/openid-configuration`` from, and an audience the token was
minted for. New providers are added by appending one entry to ``DEFAULTS``
or by setting ``WAKILI_OIDC_PROVIDERS`` (JSON) in the environment.

The frontend ships its own mirror of this list (``frontend/lib/auth/config.ts``)
— same shape, same names — so the UI and the API agree on which providers
exist.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class OIDCProvider:
    """Declarative OIDC provider config."""

    id: str
    name: str
    issuer: str
    audience: str
    jwks_uri: str | None = None
    # Optional: if the IdP minted tokens with `azp` instead of `aud=client_id`,
    # set this to the client_id Verda was issued. Leave empty to skip.
    authorized_party: str | None = None
    # Optional: extra claims to require, e.g. {"email_verified": True}.
    required_claims: dict[str, Any] = field(default_factory=dict)
    # Optional: for clock skew tolerance in seconds.
    leeway_seconds: int = 30
    # Optional: friendly description for the provider chooser.
    description: str = ""


def _from_env() -> list[OIDCProvider]:
    raw = os.getenv("WAKILI_OIDC_PROVIDERS", "").strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[OIDCProvider] = []
    for item in items:
        try:
            out.append(OIDCProvider(**item))
        except TypeError:
            continue
    return out


def _defaults() -> list[OIDCProvider]:
    """Built-in defaults wired to the docker-compose Keycloak.

    Override via WAKILI_OIDC_PROVIDERS or by editing this list. The defaults
    are deliberately permissive so the demo runs out of the box; for any real
    deployment, replace ``localhost:8080`` with your IdP host.
    """
    issuer = os.getenv("WAKILI_KEYCLOAK_ISSUER", "http://localhost:8080/realms/wakili")
    client_id = os.getenv("WAKILI_KEYCLOAK_CLIENT_ID", "wakili-frontend")
    # Default audience matches the client_id because the bundled realm ships
    # an `oidc-audience-mapper` that adds it. Override via env if your IdP
    # uses a different audience claim.
    return [
        OIDCProvider(
            id="keycloak",
            name="Keycloak (default)",
            issuer=issuer,
            audience=os.getenv("WAKILI_KEYCLOAK_AUDIENCE", client_id),
            authorized_party=client_id,
            description="Self-hosted Keycloak — federates Google, Azure, SAML, LDAP, etc.",
        ),
        # ------------------------------------------------------------------
        # Examples — uncomment / edit and they're live. The API and UI will
        # both pick them up automatically.
        # ------------------------------------------------------------------
        #
        # OIDCProvider(
        #     id="auth0",
        #     name="Auth0",
        #     issuer="https://YOUR-TENANT.auth0.com/",
        #     audience="https://wakili.example",
        #     authorized_party="YOUR_CLIENT_ID",
        #     description="Auth0 / Okta hosted identity",
        # ),
        # OIDCProvider(
        #     id="authentik",
        #     name="Authentik",
        #     issuer="https://auth.example/application/o/wakili/",
        #     audience="wakili",
        #     authorized_party="wakili-frontend",
        # ),
        # OIDCProvider(
        #     id="azure",
        #     name="Microsoft Entra ID",
        #     issuer="https://login.microsoftonline.com/YOUR_TENANT/v2.0",
        #     audience="api://wakili",
        #     authorized_party="YOUR_CLIENT_ID",
        # ),
        # OIDCProvider(
        #     id="google",
        #     name="Google",
        #     issuer="https://accounts.google.com",
        #     audience="YOUR_OAUTH_CLIENT_ID.apps.googleusercontent.com",
        # ),
    ]


@lru_cache(maxsize=1)
def list_providers() -> list[OIDCProvider]:
    return [*_defaults(), *_from_env()]


def get_provider(provider_id: str) -> OIDCProvider | None:
    for p in list_providers():
        if p.id == provider_id:
            return p
    return None


def default_provider() -> OIDCProvider:
    providers = list_providers()
    if not providers:
        raise RuntimeError("No OIDC providers configured")
    return providers[0]


def reset_cache() -> None:
    """Test hook — call after mutating environment variables."""
    list_providers.cache_clear()
