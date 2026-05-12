"use client";

/**
 * LanguagePicker — switches the UI between the locales Verda ships.
 *
 * Two layouts:
 *   variant="menu"    a stacked list, suited to the user-menu drawer.
 *   variant="inline"  a compact <select>, suited to the sign-in screen.
 *
 * Switching writes the cookie via POST /api/locale and then calls
 * `router.refresh()` so the server re-resolves the locale and re-sends
 * the layout's `<html lang>` + every translated string in the tree —
 * without nuking client state (open dialogs, scroll, half-typed forms).
 */
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { LOCALES, LOCALE_LABELS, type Locale } from "@/lib/i18n/config";
import { useIntl } from "@/lib/i18n/provider";

type Variant = "menu" | "inline";

async function persistLocale(locale: Locale): Promise<void> {
  await fetch("/api/locale", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ locale }),
    credentials: "same-origin",
  });
}

export function LanguagePicker({
  variant = "menu",
  onPicked,
}: {
  variant?: Variant;
  /** Called after a successful switch — useful for closing a parent menu. */
  onPicked?: (locale: Locale) => void;
}) {
  const { locale, t } = useIntl();
  const router = useRouter();
  const [pending, start] = useTransition();

  const apply = (next: Locale) => {
    if (next === locale) return;
    start(async () => {
      await persistLocale(next);
      router.refresh();
      onPicked?.(next);
    });
  };

  if (variant === "inline") {
    return (
      <label className="inline-flex items-center gap-2 text-xs text-ink/65">
        <span className="uppercase tracking-[0.16em]">{t("language.label")}</span>
        <select
          value={locale}
          onChange={(e) => apply(e.target.value as Locale)}
          disabled={pending}
          className="rounded-md border border-ink/15 bg-paper px-2 py-1 text-sm text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/45 disabled:opacity-60"
          aria-label={t("language.change")}
        >
          {LOCALES.map((code) => (
            <option key={code} value={code}>
              {LOCALE_LABELS[code]}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <div className="px-3 pb-2 pt-1">
      <p className="text-[10px] uppercase tracking-[0.16em] text-ink/45">
        {t("language.label")}
      </p>
      <ul role="radiogroup" aria-label={t("language.change")} className="mt-1.5 space-y-0.5">
        {LOCALES.map((code) => {
          const active = code === locale;
          return (
            <li key={code}>
              <button
                type="button"
                role="radio"
                aria-checked={active}
                disabled={pending}
                onClick={() => apply(code)}
                className={
                  "flex w-full items-center justify-between rounded-md px-2 py-1 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/45 disabled:opacity-60 " +
                  (active
                    ? "bg-paper-deep/80 text-ink"
                    : "text-ink/75 hover:bg-paper-deep/60 hover:text-ink")
                }
              >
                <span>{LOCALE_LABELS[code]}</span>
                {active ? (
                  <span aria-hidden className="text-[10px] uppercase tracking-[0.16em] text-gold">
                    ●
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
