import { NextRequest, NextResponse } from "next/server";
import { APP_BASE_URL, getProvider } from "@/lib/auth/config";
import { discover } from "@/lib/auth/oidc";
import { clearSession, readSession } from "@/lib/auth/session";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const returnTo = url.searchParams.get("returnTo") ?? "/";
  const session = await readSession();
  await clearSession();
  if (!session) return NextResponse.redirect(`${APP_BASE_URL}${returnTo}`);
  const provider = getProvider(session.providerId);
  if (!provider) return NextResponse.redirect(`${APP_BASE_URL}${returnTo}`);
  try {
    const doc = await discover(provider);
    if (doc.end_session_endpoint) {
      const endUrl = new URL(doc.end_session_endpoint);
      if (session.tokens.id_token) {
        endUrl.searchParams.set("id_token_hint", session.tokens.id_token);
      }
      endUrl.searchParams.set(
        "post_logout_redirect_uri",
        `${APP_BASE_URL.replace(/\/$/, "")}${returnTo}`
      );
      endUrl.searchParams.set("client_id", provider.clientId);
      return NextResponse.redirect(endUrl.toString());
    }
  } catch {
    /* fall through */
  }
  return NextResponse.redirect(`${APP_BASE_URL}${returnTo}`);
}
