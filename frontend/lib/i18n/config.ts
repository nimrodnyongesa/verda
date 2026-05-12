/**
 * i18n configuration — single source of truth for the locales Verda
 * ships at launch. Adding a new language is a three-step contribution:
 *
 *   1. Drop a `messages/<code>.json` catalog mirroring `en.json`.
 *   2. Append the locale to `LOCALES` below.
 *   3. (Optional) provide a native-language label in `LOCALE_LABELS`.
 *
 * No code under `app/` or `components/` needs to change.
 */

export const DEFAULT_LOCALE = "en" as const;

export const LOCALES = ["en", "sw", "fr", "ar", "pt"] as const;
export type Locale = (typeof LOCALES)[number];

/** Native-language label shown in the language picker. */
export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  sw: "Kiswahili",
  fr: "Français",
  ar: "العربية",
  pt: "Português",
};

/** Right-to-left locales — drives `<html dir>`. */
export const RTL_LOCALES: ReadonlySet<Locale> = new Set<Locale>(["ar"]);

/** Cookie name that persists the user's locale choice. */
export const LOCALE_COOKIE = "verda.locale";

/**
 * Coerce an arbitrary string into a known Locale, or return the
 * default. Used everywhere we read user input (cookie, Accept-Language,
 * URL param) so a junk value can never break the catalog lookup.
 */
export function coerceLocale(value: string | null | undefined): Locale {
  if (!value) return DEFAULT_LOCALE;
  const lower = value.toLowerCase().split(/[-_]/)[0];
  return (LOCALES as readonly string[]).includes(lower)
    ? (lower as Locale)
    : DEFAULT_LOCALE;
}
