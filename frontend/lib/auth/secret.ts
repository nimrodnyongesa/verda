// Resolve the OIDC client secret. The bundled Keycloak realm at
// `infra/keycloak/realm-wakili.json` ships with `wakili-dev-secret` for the
// `wakili-frontend` confidential client. We honour any override from env
// (KEYCLOAK_CLIENT_SECRET / WAKILI_KEYCLOAK_CLIENT_SECRET); when nothing is
// set, we fall back to the bundled-realm secret so the local demo works
// out-of-the-box even when the operator forgot to source `.env`.

const BUNDLED_DEV_SECRET = "wakili-dev-secret";

export function clientSecretFor(providerId: string): string | undefined {
  const explicit =
    process.env.KEYCLOAK_CLIENT_SECRET ||
    process.env.WAKILI_KEYCLOAK_CLIENT_SECRET ||
    process.env[`WAKILI_OIDC_SECRET_${providerId.toUpperCase()}`];
  if (explicit) return explicit;
  // Only fall back for the bundled Keycloak default. Other providers
  // require an explicit secret — we won't guess.
  if (providerId === "keycloak") return BUNDLED_DEV_SECRET;
  return undefined;
}
