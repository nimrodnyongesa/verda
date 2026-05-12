import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { APP_BASE_URL, getProvider } from "@/lib/auth/config";
import { decodeIdToken, exchangeCodeForTokens } from "@/lib/auth/oidc";
import { clientSecretFor } from "@/lib/auth/secret";
import { writeSession } from "@/lib/auth/session";

const STATE_COOKIE = "wakili.oauth.state";

function back(message: string, returnTo = "/") {
  const url = `${APP_BASE_URL.replace(/\/$/, "")}/sign-in?error=${encodeURIComponent(message)}&returnTo=${encodeURIComponent(returnTo)}`;
  return NextResponse.redirect(url);
}

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const stateParam = url.searchParams.get("state");
  const returnToParam = url.searchParams.get("returnTo") ?? "/";

  // Surface IdP-side errors directly (`?error=access_denied&error_description=…`)
  const idpError = url.searchParams.get("error");
  if (idpError) {
    const desc = url.searchParams.get("error_description") ?? idpError;
    return back(`${idpError}: ${desc}`, returnToParam);
  }
  if (!code || !stateParam) {
    return back("Missing OAuth code or state. Try signing in again.", returnToParam);
  }

  const jar = await cookies();
  const stateRaw = jar.get(STATE_COOKIE)?.value;
  if (!stateRaw) {
    return back(
      "OAuth state cookie missing or expired. Click Sign in again — your browser may have cleared it.",
      returnToParam
    );
  }
  let stored: { state: string; codeVerifier: string; providerId: string; returnTo?: string };
  try {
    stored = JSON.parse(stateRaw);
  } catch {
    jar.delete(STATE_COOKIE);
    return back("OAuth state cookie was corrupted. Try signing in again.", returnToParam);
  }
  if (stored.state !== stateParam) {
    jar.delete(STATE_COOKIE);
    return back("OAuth state mismatch (CSRF guard). Try signing in again.", stored.returnTo ?? returnToParam);
  }
  const provider = getProvider(stored.providerId);
  if (!provider) {
    return back(`Unknown identity provider: ${stored.providerId}`, stored.returnTo ?? returnToParam);
  }

  const redirectUri = `${APP_BASE_URL.replace(/\/$/, "")}/api/auth/callback`;
  let tokens;
  try {
    tokens = await exchangeCodeForTokens(
      provider,
      code,
      redirectUri,
      stored.codeVerifier,
      clientSecretFor(provider.id)
    );
  } catch (err) {
    const raw = err instanceof Error ? err.message : "exchange failed";
    let hint = raw;
    if (raw.includes("unauthorized_client") || raw.includes("Invalid client")) {
      hint =
        "Keycloak rejected our client credentials. " +
        "The bundled realm uses client secret `wakili-dev-secret`. " +
        "Either set KEYCLOAK_CLIENT_SECRET=wakili-dev-secret in .env (and restart), " +
        "or run `make stack-reset` to reload the realm. " +
        `Original error: ${raw}`;
    } else if (raw.includes("invalid_grant")) {
      hint =
        "Keycloak rejected the authorization code. This usually means the code was reused or expired. " +
        "Click Sign in again. " +
        `Original error: ${raw}`;
    }
    return back(hint, stored.returnTo ?? returnToParam);
  }

  const idClaims = tokens.id_token ? decodeIdToken(tokens.id_token) : {};
  await writeSession({
    providerId: provider.id,
    tokens,
    user: {
      sub: idClaims.sub ?? "",
      email: idClaims.email,
      name: idClaims.name ?? idClaims.preferred_username,
    },
  });
  jar.delete(STATE_COOKIE);

  const returnTo = stored.returnTo && stored.returnTo.startsWith("/") ? stored.returnTo : "/";
  return NextResponse.redirect(`${APP_BASE_URL.replace(/\/$/, "")}${returnTo}`);
}
