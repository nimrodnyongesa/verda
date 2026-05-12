import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { AUTH_ENABLED, APP_BASE_URL, defaultProvider, getProvider } from "@/lib/auth/config";
import { discover, generateRandomString, pkceChallenge } from "@/lib/auth/oidc";

const STATE_COOKIE = "wakili.oauth.state";

export async function GET(req: NextRequest) {
  if (!AUTH_ENABLED) {
    return NextResponse.json(
      { error: "Authentication is disabled. Set NEXT_PUBLIC_WAKILI_AUTH_ENABLED=true to enable." },
      { status: 503 }
    );
  }
  const url = new URL(req.url);
  const providerId = url.searchParams.get("provider") ?? defaultProvider().id;
  const provider = getProvider(providerId);
  if (!provider) {
    return NextResponse.json({ error: `Unknown provider: ${providerId}` }, { status: 400 });
  }
  const returnTo = url.searchParams.get("returnTo") ?? "/";
  let doc;
  try {
    doc = await discover(provider);
  } catch (err) {
    const cause = err instanceof Error ? err.message : String(err);
    const detail = `${provider.name} is not reachable at ${provider.issuer}. ` +
      `Start it with \`make stack\` (or \`make keycloak\`), then retry. ` +
      `Original error: ${cause}`;
    return NextResponse.redirect(
      `${APP_BASE_URL.replace(/\/$/, "")}/sign-in?error=${encodeURIComponent(detail)}&returnTo=${encodeURIComponent(returnTo)}`
    );
  }

  const state = generateRandomString(24);
  const codeVerifier = generateRandomString(48);
  const codeChallenge = await pkceChallenge(codeVerifier);
  const redirectUri = `${APP_BASE_URL.replace(/\/$/, "")}/api/auth/callback`;

  const authUrl = new URL(doc.authorization_endpoint);
  authUrl.searchParams.set("client_id", provider.clientId);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("scope", provider.scope ?? "openid profile email");
  authUrl.searchParams.set("state", state);
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  if (provider.prompt) authUrl.searchParams.set("prompt", provider.prompt);

  const jar = await cookies();
  jar.set({
    name: STATE_COOKIE,
    value: JSON.stringify({ state, codeVerifier, providerId: provider.id, returnTo }),
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });

  return NextResponse.redirect(authUrl.toString());
}
