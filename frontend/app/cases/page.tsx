import { CasesPageClient } from "@/components/cases-page-client";
import { UploadZone } from "@/components/upload-zone";
import { api } from "@/lib/api";
import type { CaseFolder, CaseSummary } from "@/lib/types";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export const dynamic = "force-dynamic";

async function fetchFolders(): Promise<CaseFolder[]> {
  // The folders endpoint is auth-gated; if the session is anonymous or
  // expired the proxy returns 401 and we fall back to an empty tree so
  // the page still renders the upload zone + sign-in CTA.
  try {
    const r = await api.listFolders();
    return r.folders;
  } catch {
    return [];
  }
}

async function fetchCases(): Promise<CaseSummary[]> {
  try {
    const r = await api.listCases();
    return r.cases;
  } catch {
    return [];
  }
}

export default async function CasesPage() {
  const [cases, folders, msg] = await Promise.all([
    fetchCases(),
    fetchFolders(),
    getMessages(),
  ]);
  const t = (key: string, vars?: Record<string, string | number>) =>
    format(msg.messages, msg.fallback, key, vars);
  // Locale-aware singular/plural — `Intl.PluralRules` returns the CLDR
  // category ("one", "other", "few", "many", "two", "zero") so the same
  // template structure works for English's two-form scheme and Arabic's
  // six-form scheme without us hand-rolling plural rules.
  const plural = new Intl.PluralRules(msg.locale).select(cases.length);
  const headingKey =
    plural === "one" ? "cases.headingOne" : "cases.headingOther";
  return (
    <div className="app-shell py-10 grid gap-6">
      <header>
        <p className="text-[11px] uppercase tracking-[0.18em] text-ink/45">
          {t("cases.kicker")}
        </p>
        <h1 className="serif mt-2 text-3xl font-bold tracking-tight">
          {t(headingKey, { count: cases.length })}
        </h1>
      </header>
      <UploadZone compact />
      <CasesPageClient initialCases={cases} initialFolders={folders} />
    </div>
  );
}
