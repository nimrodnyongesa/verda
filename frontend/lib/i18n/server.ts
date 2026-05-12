/**
 * Server-side locale resolution. Runs in the React Server Component
 * tree (so `cookies()` / `headers()` are available) — never imported
 * from a `"use client"` module.
 *
 * Resolution order:
 *   1. The `verda.locale` cookie (the user's explicit pick).
 *   2. The `Accept-Language` header on the incoming request, parsed
 *      down to the primary subtag and matched against `LOCALES`.
 *   3. `DEFAULT_LOCALE` (English).
 *
 * Returning the locale and matching catalog together lets the layout
 * pass everything the client provider needs in a single prop without
 * a second cookie/header read on the way down.
 */
import { cookies, headers } from "next/headers";
import {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_COOKIE,
  type Locale,
  coerceLocale,
} from "./config";
import { CATALOGS, FALLBACK_CATALOG } from "./catalogs";
import type { MessageBag } from "./format";

/**
 * Pick the best Locale from an `Accept-Language` header value. We don't
 * need the full RFC 4647 ranking — defenders typing on shared devices
 * benefit far more from the explicit cookie path than from q-weighted
 * negotiation.
 */
function negotiate(acceptLanguage: string | null | undefined): Locale | null {
  if (!acceptLanguage) return null;
  for (const raw of acceptLanguage.split(",")) {
    const tag = raw.trim().split(";")[0];
    if (!tag) continue;
    const primary = tag.toLowerCase().split(/[-_]/)[0];
    if ((LOCALES as readonly string[]).includes(primary)) {
      return primary as Locale;
    }
  }
  return null;
}

export async function getLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const explicit = cookieStore.get(LOCALE_COOKIE)?.value;
  if (explicit) return coerceLocale(explicit);

  const headerStore = await headers();
  const fromHeader = negotiate(headerStore.get("accept-language"));
  if (fromHeader) return fromHeader;

  return DEFAULT_LOCALE;
}

export async function getMessages(): Promise<{
  locale: Locale;
  messages: MessageBag;
  fallback: MessageBag;
}> {
  const locale = await getLocale();
  return {
    locale,
    messages: CATALOGS[locale] ?? FALLBACK_CATALOG,
    fallback: FALLBACK_CATALOG,
  };
}
