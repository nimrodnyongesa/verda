// Frontend OIDC provider registry — mirrors backend/wakili/auth/providers.py.
// Adding a provider = one entry. The UI's sign-in chooser and the OAuth flow
// both read from this list.
//
// Why hand-rolled instead of NextAuth? Two reasons:
//   1) Verda needs to forward Bearer tokens to the FastAPI backend, which is
//      simpler with explicit cookie storage than with NextAuth's encrypted JWT.
//   2) Avoiding deps keeps the air-gapped self-hosted bundle smaller.
// The flow is standard PKCE Authorization Code per RFC 7636.

export type ProviderConfig = {
  id: string;
  name: string;
  issuer: string;
  clientId: string;
  // Optional: scope override. Default: "openid profile email".
  scope?: string;
  // Optional: comma-separated list of `prompt` values (e.g. "select_account").
  prompt?: string;
  // Optional: friendly description shown on the chooser screen.
  description?: string;
};

const KC_ISSUER = process.env.KEYCLOAK_ISSUER ?? "http://localhost:8080/realms/wakili";
const KC_CLIENT = process.env.KEYCLOAK_CLIENT_ID ?? "wakili-frontend";

export const PROVIDERS: ProviderConfig[] = [
  {
    id: "keycloak",
    name: "Keycloak",
    issuer: KC_ISSUER,
    clientId: KC_CLIENT,
    description:
      "Default. Federates Google, Azure, SAML, LDAP, GitHub, etc. via Keycloak.",
  },
  // ---------------------------------------------------------------------
  // Examples — drop in and they show up immediately on the chooser screen.
  // ---------------------------------------------------------------------
  // {
  //   id: "auth0",
  //   name: "Auth0",
  //   issuer: "https://YOUR-TENANT.auth0.com/",
  //   clientId: "YOUR_CLIENT_ID",
  //   description: "Auth0 hosted identity",
  // },
  // {
  //   id: "authentik",
  //   name: "Authentik",
  //   issuer: "https://auth.example/application/o/wakili/",
  //   clientId: "wakili-frontend",
  // },
  // {
  //   id: "azure",
  //   name: "Microsoft Entra ID",
  //   issuer: "https://login.microsoftonline.com/YOUR_TENANT/v2.0",
  //   clientId: "YOUR_CLIENT_ID",
  // },
  // {
  //   id: "google",
  //   name: "Google",
  //   issuer: "https://accounts.google.com",
  //   clientId: "YOUR_OAUTH_CLIENT_ID.apps.googleusercontent.com",
  //   scope: "openid email profile",
  //   prompt: "select_account",
  // },
];

// Auth is ON by default. To run anonymously (CI / air-gapped) set
// NEXT_PUBLIC_WAKILI_AUTH_ENABLED=false explicitly.
export const AUTH_ENABLED =
  (process.env.NEXT_PUBLIC_WAKILI_AUTH_ENABLED ?? "true").toLowerCase() !== "false";

export const APP_BASE_URL = process.env.WAKILI_APP_URL ?? "http://localhost:3000";

export function getProvider(id: string): ProviderConfig | undefined {
  return PROVIDERS.find((p) => p.id === id);
}

export function defaultProvider(): ProviderConfig {
  if (!PROVIDERS.length) throw new Error("No OIDC providers configured");
  return PROVIDERS[0];
}
