// Server-side session helpers — read tokens from HTTP-only cookies, refresh on
// expiry, and surface a `Session` object to pages and route handlers.
//
// Why split across multiple cookies?
//   Keycloak access tokens routinely exceed 1.5 KB. With id_token +
//   refresh_token + user info, the full base64-JSON payload runs ~5 KB,
//   which blows past the browser's 4096-byte per-cookie limit (RFC 6265
//   §6.1). Browsers silently drop oversize cookies, so the user appeared
//   logged out and `/api/auth/me` returned `user: null` even though the
//   token exchange had succeeded.
//
//   We now write the access token, refresh token, and a small metadata
//   blob (provider id, expiry, user identity) to *separate* cookies. Each
//   one fits comfortably; reassembly happens here. The id_token is
//   deliberately not stored — its only job at runtime is seeding the
//   session.user, which we already do at exchange time.

import { cookies } from "next/headers";
import { AUTH_ENABLED, defaultProvider, getProvider } from "./config";
import { decodeIdToken, refreshTokens, TokenSet } from "./oidc";
import { clientSecretFor } from "./secret";

const COOKIE_LEGACY = "wakili.session"; // pre-split; cleared on logout for migration
const COOKIE_AT = "wakili.session.at";
const COOKIE_RT = "wakili.session.rt";
const COOKIE_META = "wakili.session.meta";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export type SessionData = {
  providerId: string;
  tokens: TokenSet;
  user: {
    sub: string;
    email?: string;
    name?: string;
  };
};

export type Session = SessionData | null;

type MetaCookie = {
  providerId: string;
  expires_at: number;
  token_type: string;
  user: SessionData["user"];
};

function encodeMeta(meta: MetaCookie): string {
  return Buffer.from(JSON.stringify(meta), "utf-8").toString("base64url");
}

function decodeMeta(raw: string | undefined): MetaCookie | null {
  if (!raw) return null;
  try {
    return JSON.parse(Buffer.from(raw, "base64url").toString("utf-8")) as MetaCookie;
  } catch {
    return null;
  }
}

const COOKIE_OPTS = {
  httpOnly: true as const,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: MAX_AGE,
};

export async function readSession(): Promise<Session> {
  if (!AUTH_ENABLED) return null;
  const jar = await cookies();
  const at = jar.get(COOKIE_AT)?.value;
  const meta = decodeMeta(jar.get(COOKIE_META)?.value);
  if (!at || !meta) return null;
  const rt = jar.get(COOKIE_RT)?.value;
  return {
    providerId: meta.providerId,
    tokens: {
      access_token: at,
      refresh_token: rt,
      expires_at: meta.expires_at,
      token_type: meta.token_type,
    },
    user: meta.user,
  };
}

export async function writeSession(session: SessionData) {
  const jar = await cookies();
  // Drop the legacy single-cookie payload if it's still hanging around so
  // a stale 5 KB cookie doesn't keep getting sent on every request.
  jar.delete(COOKIE_LEGACY);
  jar.set({ ...COOKIE_OPTS, name: COOKIE_AT, value: session.tokens.access_token });
  if (session.tokens.refresh_token) {
    jar.set({ ...COOKIE_OPTS, name: COOKIE_RT, value: session.tokens.refresh_token });
  } else {
    jar.delete(COOKIE_RT);
  }
  const meta: MetaCookie = {
    providerId: session.providerId,
    expires_at: session.tokens.expires_at,
    token_type: session.tokens.token_type,
    user: session.user,
  };
  jar.set({ ...COOKIE_OPTS, name: COOKIE_META, value: encodeMeta(meta) });
}

export async function clearSession() {
  const jar = await cookies();
  jar.delete(COOKIE_LEGACY);
  jar.delete(COOKIE_AT);
  jar.delete(COOKIE_RT);
  jar.delete(COOKIE_META);
}

export async function getSession(): Promise<Session> {
  const session = await readSession();
  if (!session) return null;

  // Refresh if access token expired (or expiring within 30s).
  const now = Math.floor(Date.now() / 1000);
  if (session.tokens.expires_at - 30 > now) return session;

  if (!session.tokens.refresh_token) return null;
  const provider = getProvider(session.providerId) ?? defaultProvider();
  try {
    const tokens = await refreshTokens(
      provider,
      session.tokens.refresh_token,
      clientSecretFor(provider.id)
    );
    const next: SessionData = { ...session, tokens };
    if (tokens.id_token) {
      const id = decodeIdToken(tokens.id_token);
      next.user = {
        sub: id.sub ?? session.user.sub,
        email: id.email ?? session.user.email,
        name: id.name ?? id.preferred_username ?? session.user.name,
      };
    }
    await writeSession(next);
    return next;
  } catch {
    await clearSession();
    return null;
  }
}

export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  return session?.tokens.access_token ?? null;
}
