import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export default async function AboutPage() {
  const { messages, fallback } = await getMessages();
  const t = (key: string, vars?: Record<string, string | number>) =>
    format(messages, fallback, key, vars);
  return (
    <div className="mx-auto max-w-3xl px-6 py-12 grid gap-6">
      <header>
        <p className="text-xs uppercase tracking-[0.22em] text-gold">{t("about.kicker")}</p>
        <h1 className="serif mt-2 text-3xl font-bold">{t("about.title")}</h1>
      </header>

      <section className="grid gap-3 text-sm leading-relaxed text-ink/80">
        <p>{t("about.intro1")}</p>
        <p>{t("about.intro2")}</p>
        <p>
          {t("about.intro3Prefix")}
          <code className="mono">AGENTS.md</code>
          {t("about.intro3Suffix")}
        </p>
      </section>

      <section className="rounded-xl border border-ink/10 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">{t("about.architectureTitle")}</h2>
        <ul className="mt-2 grid gap-2 text-sm">
          {(["intake", "knowledge", "orchestration", "generation", "deployment"] as const).map((k) => (
            <li key={k}>
              <strong>{t(`about.architecture.${k}.label`)}</strong> — {t(`about.architecture.${k}.body`)}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-ink/10 bg-paper-deep/40 p-5">
        <h2 className="font-semibold">{t("about.lawyerTitle")}</h2>
        <p className="mt-2 text-sm text-ink/80">{t("about.lawyerBody")}</p>
      </section>
    </div>
  );
}
