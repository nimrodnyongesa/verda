/**
 * Static catalog registry. Imported synchronously so server components
 * can read messages without an awaitable boundary, and the TypeScript
 * compiler verifies that every locale in `LOCALES` has a matching
 * JSON file at build time.
 *
 * The bundler tree-shakes per-route imports, but for chrome strings
 * (header / footer / nav) we want every locale resident in the same
 * chunk so the language picker switches without a network round-trip.
 */
import type { MessageBag } from "./format";
import { DEFAULT_LOCALE, type Locale } from "./config";

import en from "./messages/en.json";
import sw from "./messages/sw.json";
import fr from "./messages/fr.json";
import ar from "./messages/ar.json";
import pt from "./messages/pt.json";

export const CATALOGS: Record<Locale, MessageBag> = {
  en: en as MessageBag,
  sw: sw as MessageBag,
  fr: fr as MessageBag,
  ar: ar as MessageBag,
  pt: pt as MessageBag,
};

/** The English catalog is the always-on fallback. */
export const FALLBACK_CATALOG: MessageBag = CATALOGS[DEFAULT_LOCALE];

export function getCatalog(locale: Locale): MessageBag {
  return CATALOGS[locale] ?? FALLBACK_CATALOG;
}
