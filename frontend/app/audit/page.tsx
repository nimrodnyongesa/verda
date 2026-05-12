import { AuditPanel } from "@/components/panels/audit-panel";
import { api } from "@/lib/api";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export const dynamic = "force-dynamic";

export default async function GlobalAuditPage() {
  const [result, msg] = await Promise.all([
    api.audit().catch(() => ({ entries: [] })),
    getMessages(),
  ]);
  const t = (key: string) => format(msg.messages, msg.fallback, key);
  return (
    <div className="mx-auto max-w-6xl px-6 py-10 grid gap-4">
      <header>
        <p className="text-[11px] uppercase tracking-[0.18em] text-ink/45">{t("audit.kicker")}</p>
        <h1 className="serif mt-2 text-3xl font-bold tracking-tight">{t("audit.title")}</h1>
        <p className="mt-1 text-sm text-ink/60">{t("audit.body")}</p>
      </header>
      <AuditPanel entries={result.entries} />
    </div>
  );
}
