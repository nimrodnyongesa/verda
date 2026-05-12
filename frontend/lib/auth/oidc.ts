// OIDC discovery + PKCE helpers (server-side only).

import { ProviderConfig } from "./config";

type DiscoveryDoc = {
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint?: string;
  userinfo_endpoint?: string;
  jwks_uri?: string;
};

const cache = new Map<string, { at: number; doc: DiscoveryDoc }>();
const TTL_MS = 10 * 60 * 1000;

export async function discover(provider: ProviderConfig): Promise<DiscoveryDoc> {
  const now = Date.now();
  const hit = cache.get(provider.id);
  if (hit && now - hit.at < TTL_MS) return hit.doc;
  const url = provider.issuer.replace(/\/$/, "") + "/.well-known/openid-configuration";
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`OIDC discovery failed for ${provider.id}: HTTP ${res.status}`);
  const doc = (await res.json()) as DiscoveryDoc;
  cache.set(provider.id, { at: now, doc });
  return doc;
}

function base64url(buffer: ArrayBuffer): string {
  return Buffer.from(buffer)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export function generateRandomString(bytes = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)).buffer as ArrayBuffer);
}

export async function pkceChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64url(digest);
}

export type TokenSet = {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  expires_at: number;
  token_type: string;
};

export async function exchangeCodeForTokens(
  provider: ProviderConfig,
  code: string,
  redirectUri: string,
  codeVerifier: string,
  clientSecret?: string
): Promise<TokenSet> {
  const doc = await discover(provider);
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: provider.clientId,
    code,
    redirect_uri: redirectUri,
    code_verifier: codeVerifier,
  });
  if (clientSecret) body.set("client_secret", clientSecret);
  const res = await fetch(doc.token_endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Token exchange failed (${res.status}): ${text}`);
  }
  const j = (await res.json()) as {
    access_token: string;
    id_token?: string;
    refresh_token?: string;
    expires_in?: number;
    token_type?: string;
  };
  return {
    access_token: j.access_token,
    id_token: j.id_token,
    refresh_token: j.refresh_token,
    expires_at: Math.floor(Date.now() / 1000) + (j.expires_in ?? 60),
    token_type: j.token_type ?? "Bearer",
  };
}

export async function refreshTokens(
  provider: ProviderConfig,
  refreshToken: string,
  clientSecret?: string
): Promise<TokenSet> {
  const doc = await discover(provider);
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: provider.clientId,
    refresh_token: refreshToken,
  });
  if (clientSecret) body.set("client_secret", clientSecret);
  const res = await fetch(doc.token_endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Refresh failed (${res.status}): ${text}`);
  }
  const j = (await res.json()) as {
    access_token: string;
    id_token?: string;
    refresh_token?: string;
    expires_in?: number;
    token_type?: string;
  };
  return {
    access_token: j.access_token,
    id_token: j.id_token,
    refresh_token: j.refresh_token ?? refreshToken,
    expires_at: Math.floor(Date.now() / 1000) + (j.expires_in ?? 60),
    token_type: j.token_type ?? "Bearer",
  };
}

export function decodeIdToken(idToken: string): {
  sub?: string;
  email?: string;
  name?: string;
  preferred_username?: string;
  exp?: number;
} {
  const parts = idToken.split(".");
  if (parts.length < 2) return {};
  try {
    const payload = Buffer.from(parts[1].replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf-8");
    return JSON.parse(payload);
  } catch {
    return {};
  }
}
