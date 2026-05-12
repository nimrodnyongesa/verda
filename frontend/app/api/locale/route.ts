/**
 * Locale-cookie endpoint. Persists the user's language pick across
 * sessions and devices that share the cookie jar.
 *
 *   POST /api/locale  body: { locale: "en" | "sw" | "fr" | "ar" | "pt" }
 *
 * Sets `verda.locale` (HttpOnly is *not* set — the client `LanguagePicker`
 * still benefits from `router.refresh()` regardless, but exposing the
 * cookie keeps the door open for a future client-side optimistic switch
 * that updates messages before the server round-trip completes).
 *
 * GET returns the currently resolved locale (cookie ▸ Accept-Language
 * ▸ default) so a debug surface or external tool can introspect.
 */
import { NextResponse } from "next/server";
import { coerceLocale, LOCALE_COOKIE, LOCALES } from "@/lib/i18n/config";
import { getLocale } from "@/lib/i18n/server";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

export async function GET() {
  const locale = await getLocale();
  return NextResponse.json({ locale, supported: LOCALES });
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const requested =
    body && typeof body === "object" && "locale" in body
      ? (body as { locale?: unknown }).locale
      : undefined;
  if (typeof requested !== "string") {
    return NextResponse.json({ error: "missing_locale" }, { status: 400 });
  }
  const locale = coerceLocale(requested);
  const res = NextResponse.json({ locale });
  res.cookies.set(LOCALE_COOKIE, locale, {
    path: "/",
    maxAge: ONE_YEAR_SECONDS,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
  return res;
}
