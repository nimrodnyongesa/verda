"""OIDC token verification.

Uses PyJWT's standard JWKS client to fetch + cache signing keys, then verifies
RS256/ES256 access tokens against the issuer in ``providers.py``.

The discovery doc is fetched once and cached for 10 minutes; signing keys are
cached by JWT ``kid`` (PyJWT handles rotation transparently).
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import jwt
from jwt import PyJWKClient

from .providers import OIDCProvider, get_provider, list_providers

_DISCOVERY_TTL = 600  # seconds
_JWKS_CACHE_LIFE = 3600
_discovery_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_clients: dict[str, PyJWKClient] = {}


class TokenError(Exception):
    """Token failed verification."""


def _discovery(provider: OIDCProvider) -> dict[str, Any]:
    now = time.time()
    cached = _discovery_cache.get(provider.id)
    if cached and now - cached[0] < _DISCOVERY_TTL:
        return cached[1]
    url = provider.issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise TokenError(f"Cannot fetch OIDC discovery for {provider.id}: {exc}") from exc
    _discovery_cache[provider.id] = (now, data)
    return data


def _jwks_client(provider: OIDCProvider) -> PyJWKClient:
    client = _jwks_clients.get(provider.id)
    if client is not None:
        return client
    jwks_uri = provider.jwks_uri or _discovery(provider).get("jwks_uri")
    if not jwks_uri:
        raise TokenError(f"No jwks_uri available for {provider.id}")
    client = PyJWKClient(jwks_uri, cache_keys=True, lifespan=_JWKS_CACHE_LIFE)
    _jwks_clients[provider.id] = client
    return client


def _select_provider(token: str) -> OIDCProvider:
    """Pick the right provider based on the unverified ``iss`` claim."""
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise TokenError(f"Token is not a JWT: {exc}") from exc
    iss = unverified.get("iss")
    if not iss:
        raise TokenError("Token has no iss claim")
    for p in list_providers():
        if p.issuer.rstrip("/") == iss.rstrip("/"):
            return p
    raise TokenError(f"No provider configured for iss={iss}")


def verify_token(token: str, *, provider_id: str | None = None) -> dict[str, Any]:
    """Validate a Bearer access token and return the claims dict.

    If ``provider_id`` is given, that provider is used. Otherwise we infer
    it from the unverified ``iss`` claim and match against the registry.
    """
    if not token:
        raise TokenError("Empty token")
    provider = get_provider(provider_id) if provider_id else _select_provider(token)
    if provider is None:
        raise TokenError(f"Unknown provider: {provider_id}")

    try:
        signing_key = _jwks_client(provider).get_signing_key_from_jwt(token).key
    except Exception as exc:  # noqa: BLE001
        raise TokenError(f"Cannot resolve signing key: {exc}") from exc

    # `sub` is required by spec but Keycloak 25 may omit it from access
    # tokens unless explicitly mapped. We require iss/iat/exp here and
    # synthesise sub from `preferred_username` / `email` below if missing.
    options = {"require": ["exp", "iat", "iss"]}
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256", "EdDSA"],
            audience=provider.audience,
            issuer=provider.issuer,
            leeway=provider.leeway_seconds,
            options=options,
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise TokenError(f"Audience mismatch: expected {provider.audience}") from exc
    except jwt.PyJWTError as exc:
        raise TokenError(f"Token verification failed: {exc}") from exc

    if provider.authorized_party:
        azp = claims.get("azp")
        if azp and azp != provider.authorized_party:
            raise TokenError(f"Authorized party mismatch (azp={azp})")

    if not claims.get("sub"):
        # Synthesise from preferred_username / email so the rest of the
        # stack (audit log, ownership) has a stable identifier.
        synth = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
            or claims.get("oid")
        )
        if not synth:
            raise TokenError("Token has no sub / preferred_username / email")
        claims["sub"] = synth

    for key, expected in provider.required_claims.items():
        if claims.get(key) != expected:
            raise TokenError(f"Required claim {key} != {expected}")

    return claims
