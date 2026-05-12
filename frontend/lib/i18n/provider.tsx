"use client";

/**
 * Client-side i18n surface — a React context that holds the active
 * locale + its catalog and exposes a `useT()` hook for components.
 *
 * The provider is dumb on purpose: the server has already resolved
 * the locale (cookie / Accept-Language) before SSR, so the client
 * never has to "discover" it after mount and the user never sees an
 * English-flash followed by their language. Switching locale is a
 * cookie POST + `router.refresh()` (see `LanguagePicker`), which keeps
 * the React tree, scroll, and form state intact.
 */
import { createContext, useCallback, useContext, useMemo } from "react";
import {
  DEFAULT_LOCALE,
  LOCALE_LABELS,
  RTL_LOCALES,
  type Locale,
} from "./config";
import { format, type MessageBag, type Vars } from "./format";
import { FALLBACK_CATALOG } from "./catalogs";

type IntlValue = {
  locale: Locale;
  /** Localised name of the current locale ("English", "Kiswahili"). */
  localeLabel: string;
  /** "ltr" or "rtl" — apply to `<html dir>` on the server. */
  dir: "ltr" | "rtl";
  /** Translate a dotted key. Missing keys fall through to English. */
  t: (key: string, vars?: Vars) => string;
};

const IntlContext = createContext<IntlValue | null>(null);

export function IntlProvider({
  locale,
  messages,
  children,
}: {
  locale: Locale;
  messages: MessageBag;
  children: React.ReactNode;
}) {
  const t = useCallback(
    (key: string, vars?: Vars) =>
      format(messages, FALLBACK_CATALOG, key, vars),
    [messages],
  );

  const value = useMemo<IntlValue>(
    () => ({
      locale,
      localeLabel: LOCALE_LABELS[locale] ?? LOCALE_LABELS[DEFAULT_LOCALE],
      dir: RTL_LOCALES.has(locale) ? "rtl" : "ltr",
      t,
    }),
    [locale, t],
  );

  return <IntlContext.Provider value={value}>{children}</IntlContext.Provider>;
}

/**
 * Subscribe to the active locale + translation function. Throws if
 * called outside an `IntlProvider` so a missing wrap is a build-time
 * error during dev rather than a string of literal `header.cases`
 * leaking into the UI.
 */
export function useIntl(): IntlValue {
  const ctx = useContext(IntlContext);
  if (!ctx) {
    throw new Error("useIntl() called outside <IntlProvider>");
  }
  return ctx;
}

/** Convenience hook for the common case — only need the `t` function. */
export function useT(): IntlValue["t"] {
  return useIntl().t;
}
