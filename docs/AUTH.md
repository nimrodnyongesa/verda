# Verda — authentication & SSO

Verda runs **anonymously by default** so the local demo flow needs zero
identity setup. When you flip the auth flag, every API call is verified
against an OpenID Connect identity provider; the default ships with Keycloak.

## What ships

- **Keycloak realm** (`infra/keycloak/realm-wakili.json`) with two demo users
  (`advocate / advocate`, `paralegal / paralegal`) and a confidential client
  `wakili-frontend` with PKCE.
- **Backend OIDC verifier** (`backend/wakili/auth/`) — RS256 / ES256 / EdDSA
  via PyJWT's JWKS client. Validates `iss`, `aud`, `exp`, optional `azp`,
  and any extra required claims declared per provider.
- **Frontend OIDC client** (`frontend/lib/auth/`, `frontend/app/api/auth/*`)
  — hand-rolled Authorization Code + PKCE. Tokens stored in HTTP-only
  `wakili.session` cookie. Auto-refresh on expiry.
- **Authenticated proxy** (`/api/be/[...path]`) — forwards browser-originated
  calls to the FastAPI backend with the session's access token as Bearer.
- **Sign-in chooser** (`/sign-in`) — lists every configured provider; one
  click per provider.
- **User menu** in the header — sign-in / sign-out, identity, provider id.

## Bring it up

Verda authenticates by default — there is no anonymous mode in normal
use. You need only Docker; everything else is wired by the realm import.

### Recommended — one command

```bash
make stack       # Keycloak + backend + frontend, all wired for SSO
make smoke       # walks the full sign-in + API flow end-to-end (8 checks)
make stack-down  # stop everything
```

`make stack` blocks until all three services are healthy, then prints
the seeded demo credentials. Logs land at `/tmp/wakili-{backend,frontend}.log`.

### Demo / test credentials (seeded by the realm import)

| Username | Password | Realm role |
| --- | --- | --- |
| `advocate` | `advocate` | `lawyer` |
| `paralegal` | `paralegal` | `paralegal` |
| `nimrod` | `nimrod` | `admin`, `lawyer` |

Use `advocate / advocate` for the standard demo flow. `nimrod` adds
the `admin` realm role for `Depends(require_role("admin"))` checks. The
client secret in `.env.example` (`wakili-dev-secret`) matches the realm.

### Manual bring-up

```bash
# 1. Boot Keycloak (first time pulls ~600MB; ~30s to ready). The make target
#    waits for OIDC discovery to come online before returning.
make keycloak

# 2. Copy the example env. Auth is ON by default; nothing else to flip.
cp .env.example .env

# 3. Boot the app. `source .env` exports everything Verda needs.
source .env && make backend         # shell A
source .env && make frontend        # shell B

# 4. http://localhost:3000 → Sign in with one of the demo credentials.
```

Verda stores the session cookie (HTTP-only, SameSite=Lax), the `/api/be`
proxy forwards Bearer to FastAPI, FastAPI verifies against Keycloak's JWKS.

### Anonymous mode (offline / CI only)

To bypass auth — only for offline CI or air-gapped boxes — set both flags
to `false`:

```bash
WAKILI_AUTH_ENABLED=false NEXT_PUBLIC_WAKILI_AUTH_ENABLED=false make backend
```

This is *not* the default. `make smoke` requires auth to be on.

### Sanity check

```bash
make auth-status                    # pings Keycloak + backend + frontend

# Mint a token via password grant on the public PKCE client (testing only):
TOKEN=$(curl -sf -X POST http://localhost:8080/realms/wakili/protocol/openid-connect/token \
  -d "client_id=wakili-public&grant_type=password&username=advocate&password=advocate&scope=openid profile email" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/api/cases               # 401
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/cases  # 200
curl -sf -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/auth/whoami      # {sub, email, name, roles}
```

### What Keycloak's realm import sets up for you

The realm at `infra/keycloak/realm-wakili.json` is loaded automatically on
first boot. It contains:

| Item | Value | Why |
| --- | --- | --- |
| Realm | `wakili` | The Verda tenant |
| Confidential client | `wakili-frontend` (PKCE on; secret in `.env.example`) | Browser code-flow for the Next.js app |
| Public PKCE client | `wakili-public` (direct access grants on) | Lets you mint tokens for CLI / integration tests without a browser |
| Audience mapper | `aud: wakili-frontend` baked into the access token | Matches `WAKILI_KEYCLOAK_AUDIENCE` |
| `sub` mapper | injects `sub` into access token | Keycloak 25 omits it by default |
| Demo users | `advocate / advocate` (role `lawyer`), `paralegal / paralegal` (role `paralegal`), `nimrod / nimrod` (roles `admin` + `lawyer`) | One-click sign-in for the demo |
| Realm roles | `lawyer`, `paralegal`, `admin` | Drives `Depends(require_role(...))` checks in the backend |
| Redirect URIs | `http://{localhost,127.0.0.1}:3000/api/auth/callback` | Where Keycloak sends the auth code |
| Web origins | `http://{localhost,127.0.0.1}:3000` | CORS allowance |

### Local-only checklist (TL;DR)

1. `docker --version` works.
2. `make stack` (or `make keycloak && cp .env.example .env && make backend & make frontend &`).
3. `make smoke` to verify everything end-to-end.
4. Open http://localhost:3000, click **Sign in**, pick Keycloak,
   `advocate / advocate`, you're in.

Nothing else. Auth is ON by default.

## Adding another provider

Both registries follow the same shape. The frontend mirror controls the
**Sign in** chooser; the backend registry controls token verification.

### 1. Frontend — `frontend/lib/auth/config.ts`

```ts
export const PROVIDERS: ProviderConfig[] = [
  // existing entries...
  {
    id: "auth0",
    name: "Auth0",
    issuer: "https://YOUR-TENANT.auth0.com/",
    clientId: "YOUR_CLIENT_ID",
    description: "Auth0 hosted identity",
  },
];
```

### 2. Backend — `backend/wakili/auth/providers.py`

```python
OIDCProvider(
    id="auth0",
    name="Auth0",
    issuer="https://YOUR-TENANT.auth0.com/",
    audience="https://wakili.example",
    authorized_party="YOUR_CLIENT_ID",
    description="Auth0 hosted identity",
),
```

That's it. The provider shows up on `/sign-in`, the backend accepts tokens
from it, and the existing flow handles everything else (token refresh,
logout, audit logging).

`WAKILI_OIDC_PROVIDERS` accepts a JSON array if you'd rather configure
providers via environment variables instead of editing source.

## Standard protocols

OpenID Connect Discovery (`.well-known/openid-configuration`) means any
RFC 8414 / OIDC-compliant IdP works without code changes — Auth0,
Authentik, Okta, Microsoft Entra ID, AWS Cognito, Google, Apple. Tested
shapes are documented inline in `providers.py`.

For non-OIDC protocols (SAML 2.0, LDAP, Kerberos, social GitHub OAuth,
WebAuthn-only flows), federate them inside Keycloak under
**Identity providers** in the admin console. Keycloak then issues an OIDC
token Verda recognises — no Verda-side changes needed.

## Production notes

- Replace `change-me-in-production` in `realm-wakili.json` with a strong
  client secret (or use the public PKCE client only).
- Run Keycloak behind TLS. The `start-dev` mode in the compose file is
  development-only; for production use `start --optimized` with a Postgres
  backing store and a reverse proxy.
- Set `secure: true` on the session cookie (already wired via `NODE_ENV`).
- Rotate JWT signing keys regularly in Keycloak — Verda's JWKS client
  picks up the new keys automatically.
- Audit log records every Bearer-validated request and every MCP call —
  visible per-case at `/cases/<id>?view=audit` and globally at `/audit`.
