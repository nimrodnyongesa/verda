import Image from "next/image";
import Link from "next/link";
import { UploadZone } from "@/components/upload-zone";
import { CaseList } from "@/components/case-list";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { AUTH_ENABLED } from "@/lib/auth/config";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/magic/blur-fade";
import { NumberTicker } from "@/components/magic/number-ticker";
import { AnimatedGrid } from "@/components/magic/animated-grid";
import { DotPattern } from "@/components/magic/dot-pattern";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";
import type { MessageBag } from "@/lib/i18n/format";

export const dynamic = "force-dynamic";

type CasesResult =
  | { kind: "ok"; cases: import("@/lib/types").CaseSummary[] }
  | { kind: "anonymous" }
  | { kind: "down"; reason: string };

async function fetchCases(): Promise<CasesResult> {
  // When auth is on but the user has no session yet, /api/cases returns 401.
  // Don't surface that as "backend down" — show a sign-in CTA.
  if (AUTH_ENABLED) {
    const session = await getSession().catch(() => null);
    if (!session) return { kind: "anonymous" };
  }
  try {
    const r = await api.listCases();
    return { kind: "ok", cases: r.cases };
  } catch (err) {
    return { kind: "down", reason: err instanceof Error ? err.message : "unreachable" };
  }
}

const STAT_KEYS = [
  { key: "killed",  value: 324, prefix: "",      suffix: "" },
  { key: "backlog", value: 598, prefix: "",      suffix: "K" },
  { key: "ratio",   value: 87,  prefix: "1 : ",  suffix: "K" },
  { key: "cost",    value: 15,  prefix: "~$",    suffix: "" },
] as const;

const EVIDENCE_KEYS = [
  "policeObs", "whatsapp", "voiceNotes", "phonePhotos", "medical",
  "bankSlips", "courtRecords", "scannedPdfs", "familyThreads", "exif",
] as const;

type T = (key: string, vars?: Record<string, string | number>) => string;

export default async function Home() {
  const [cases, msg] = await Promise.all([fetchCases(), getMessages()]);
  const t: T = (key, vars) => format(msg.messages, msg.fallback, key, vars);
  return (
    <>
      <Hero t={t} />
      <ImpactPartner t={t} />
      <section className="app-shell grid gap-8 sm:gap-10 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] pretty">
        <div className="grid gap-4">
          <BlurFade>
            <h2 className="serif text-2xl font-semibold tracking-tight">{t("home.start.title")}</h2>
            <p className="mt-1 text-sm text-ink/60">{t("home.start.body")}</p>
          </BlurFade>
          {cases.kind === "anonymous" ? (
            <div className="rounded-lg border border-gold/40 bg-gold-soft/40 px-4 py-3 text-sm text-ink">
              <p className="font-semibold">{t("home.start.anonymousTitle")}</p>
              <p className="mt-1 text-ink/70">{t("home.start.anonymousBody")}</p>
              <Link
                href="/sign-in?returnTo=/"
                className="mt-2 inline-flex min-h-[40px] items-center gap-1.5 rounded-lg bg-ink px-3 py-2 text-xs font-medium text-paper hover:bg-ink-soft focus-ring"
              >
                {t("home.start.anonymousCta")}
              </Link>
            </div>
          ) : null}
          {cases.kind === "down" ? (
            <BackendDown t={t} reason={cases.reason} />
          ) : null}
          <BlurFade delay={80}>
            <UploadZone />
          </BlurFade>
          {cases.kind === "ok" ? (
            <BlurFade delay={140}>
              <div>
                <div className="mb-2 mt-6 flex items-baseline justify-between">
                  <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45">
                    {t("home.start.recentCases")}
                  </h3>
                  <Link
                    href="/cases"
                    className="text-xs text-ink/60 hover:text-ink underline-offset-2 hover:underline"
                  >
                    {t("home.start.seeAll")}
                  </Link>
                </div>
                <CaseList cases={cases.cases.slice(0, 5)} />
              </div>
            </BlurFade>
          ) : null}
        </div>

        <aside className="grid gap-4">
          <BlurFade delay={120}>
            <Card title={t("home.modules.title")} motif="/motif-evidence.svg" motifAlt="">
              <ul className="grid gap-3 text-sm">
                <ModuleRow name={t("home.modules.evidence.name")}    desc={t("home.modules.evidence.desc")} />
                <ModuleRow name={t("home.modules.procedural.name")}  desc={t("home.modules.procedural.desc")} />
                <ModuleRow name={t("home.modules.precedent.name")}   desc={t("home.modules.precedent.desc")} />
                <ModuleRow name={t("home.modules.safety.name")}      desc={t("home.modules.safety.desc")} />
              </ul>
            </Card>
          </BlurFade>
          <BlurFade delay={200}>
            <Card title={t("home.lawyer.title")} motif="/motif-scales.svg" motifAlt="">
              <p className="text-sm text-ink/70 leading-relaxed">
                {t("home.lawyer.bodyPrefix")}{" "}
                <strong>{t("home.lawyer.boundary")}</strong>{" "}
                {t("home.lawyer.bodySuffix")}
              </p>
            </Card>
          </BlurFade>
        </aside>
      </section>

      <EvidenceTypes t={t} messages={msg.messages} fallback={msg.fallback} />
    </>
  );
}

function BackendDown({ t, reason }: { t: T; reason: string }) {
  return (
    <p className="rounded-md border border-rust/40 bg-rust/5 px-3 py-2 text-sm text-rust">
      {t("home.start.backendDownTitle")}{" "}
      {t("home.start.backendDownBody", {
        makeStack: "make stack",
        makeBackend: "make backend",
      })
        .split(/(make stack|make backend)/)
        .map((seg, i) =>
          seg === "make stack" || seg === "make backend" ? (
            <code key={i} className="mono">
              {seg}
            </code>
          ) : (
            <span key={i}>{seg}</span>
          ),
        )}
      <br />
      <span className="text-rust/65 text-[11px]">{reason}</span>
    </p>
  );
}

function Hero({ t }: { t: T }) {
  return (
    <section className="relative overflow-hidden bg-ink text-paper">
      <div className="absolute inset-0 text-paper/30">
        <AnimatedGrid />
      </div>
      <div className="absolute inset-0 text-gold/40">
        <DotPattern size={28} dot={1} />
      </div>
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-b from-transparent to-paper" />
      <div className="app-shell relative grid gap-8 pt-10 pb-20 sm:pt-14 sm:pb-28 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-center lg:gap-12">
        <div>
          <BlurFade>
            <h1 className="serif max-w-3xl text-3xl font-bold leading-[1.1] tracking-tight balanced sm:text-5xl sm:leading-[1.05] md:text-6xl">
              {t("home.hero.titlePrefix")}{" "}
              <span className="shimmer-text">{t("home.hero.titleAccent")}</span>
            </h1>
          </BlurFade>
          <BlurFade delay={120}>
            <p className="mt-5 max-w-2xl text-paper/80 leading-relaxed">{t("home.hero.body")}</p>
          </BlurFade>
          <BlurFade delay={200}>
            <div className="mt-7 flex flex-wrap items-center gap-2">
              <Badge variant="gold">{t("home.hero.badge")}</Badge>
            </div>
          </BlurFade>
          <BlurFade delay={260}>
            <dl className="mt-8 grid grid-cols-2 gap-2.5 sm:mt-10 sm:gap-3 sm:grid-cols-4">
              {STAT_KEYS.map((s) => (
                <div key={s.key} className="rounded-xl border border-paper/10 bg-paper/5 px-3 py-2.5 backdrop-blur-sm sm:px-4 sm:py-3">
                  <dd className="serif text-2xl font-bold text-gold sm:text-3xl">
                    {s.prefix}
                    <NumberTicker value={s.value} />
                    {s.suffix}
                  </dd>
                  <dt className="mt-1 text-[11px] uppercase tracking-[0.14em] text-paper/60">
                    {t(`home.stats.${s.key}`)}
                  </dt>
                </div>
              ))}
            </dl>
          </BlurFade>
        </div>
        <BlurFade delay={120}>
          <div className="relative mx-auto w-full max-w-md lg:max-w-none">
            <div
              aria-hidden="true"
              className="absolute -inset-x-6 -inset-y-8 rounded-[2rem] bg-gold/10 blur-2xl"
            />
            <Image
              src="/hero-illustration.svg"
              alt="Stack of case documents converging into a Verda-marked petition, in front of a courthouse silhouette"
              width={480}
              height={540}
              priority
              className="relative w-full h-auto drop-shadow-[0_30px_60px_rgba(0,0,0,0.45)]"
            />
          </div>
        </BlurFade>
      </div>
    </section>
  );
}

function ImpactPartner({ t }: { t: T }) {
  const partner = t("home.impact.partnerName");
  const body = t("home.impact.body", { partner });
  // Bold the partner name wherever it appears in the localised body so the
  // emphasis survives translation.
  const parts = body.split(partner);
  return (
    <section className="app-shell -mt-2 mb-12 sm:-mt-4">
      <BlurFade>
        <div className="grid items-center gap-5 rounded-2xl border border-ink/10 bg-paper/80 p-5 sm:grid-cols-[auto_1fr] sm:gap-7 sm:p-6">
          <div className="flex items-center justify-center sm:justify-start">
            <Image
              src="/partners/osf-placeholder.svg"
              alt={t("home.impact.logoAlt")}
              width={200}
              height={68}
              className="h-16 w-auto sm:h-[68px]"
            />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-ink/45">
              {t("home.impact.kicker")}
            </p>
            <p className="mt-1.5 max-w-2xl text-sm text-ink/75 leading-relaxed pretty">
              {parts.map((p, i) => (
                <span key={i}>
                  {p}
                  {i < parts.length - 1 ? (
                    <span className="font-semibold text-ink">{partner}</span>
                  ) : null}
                </span>
              ))}
            </p>
          </div>
        </div>
      </BlurFade>
    </section>
  );
}

function ModuleRow({ name, desc }: { name: string; desc: string }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-gold ring-4 ring-gold/15" />
      <div>
        <span className="font-medium text-ink">{name}</span>
        <p className="text-xs text-ink/55 mt-0.5">{desc}</p>
      </div>
    </li>
  );
}

function Card({
  title,
  children,
  motif,
  motifAlt,
}: {
  title: string;
  children: React.ReactNode;
  motif?: string;
  motifAlt?: string;
}) {
  return (
    <section className="surface relative p-5">
      {motif ? (
        <Image
          src={motif}
          alt={motifAlt ?? ""}
          width={68}
          height={68}
          aria-hidden={motifAlt ? undefined : true}
          className="pointer-events-none absolute right-3 top-3 h-14 w-14 opacity-60"
        />
      ) : null}
      <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-3">{title}</h3>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Evidence types — each item's name + sub now come from the catalog so the
// chips read in the user's language. The icons are kept in code as React
// nodes (visual identity is global). Order is preserved across locales by
// the EVIDENCE_KEYS array above so what an English reader sees ranked first
// is the same item a Swahili reader sees first.
// ---------------------------------------------------------------------------

function EvidenceTypes({
  t,
  messages,
  fallback,
}: {
  t: T;
  messages: MessageBag;
  fallback: MessageBag;
}) {
  // Fallback-aware: if a future-added key is missing in the active locale,
  // we still render the English label rather than the literal key string.
  const _ = { messages, fallback };
  void _;
  return (
    <section className="app-shell mt-24">
      <BlurFade>
        <p className="text-[11px] uppercase tracking-[0.18em] text-ink/45">
          {t("home.evidenceTypes.kicker")}
        </p>
        <h2 className="serif mt-2 text-2xl font-semibold tracking-tight balanced sm:text-3xl">
          {t("home.evidenceTypes.title")}
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-ink/60 leading-relaxed">
          {t("home.evidenceTypes.body")}
        </p>
      </BlurFade>
      <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5">
        {EVIDENCE_KEYS.map((k, i) => (
          <BlurFade key={k} delay={i * 40}>
            <li className="surface flex flex-col gap-2 p-4 transition hover:border-gold/40 hover:shadow-[0_12px_28px_-18px_rgba(212,165,52,0.5)]">
              <span
                aria-hidden="true"
                className="grid h-9 w-9 place-items-center rounded-lg bg-paper-deep/70 text-ink"
              >
                <span className="block h-5 w-5">
                  <EvidenceIcon kind={k} />
                </span>
              </span>
              <span className="font-medium text-sm text-ink leading-tight">
                {t(`home.evidenceTypes.items.${k}.name`)}
              </span>
              <span className="mono text-[10px] uppercase tracking-[0.12em] text-ink/45">
                {t(`home.evidenceTypes.items.${k}.sub`)}
              </span>
            </li>
          </BlurFade>
        ))}
      </ul>
    </section>
  );
}

function EvidenceIcon({ kind }: { kind: (typeof EVIDENCE_KEYS)[number] }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5 as const,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (kind) {
    case "policeObs":
      return (
        <svg {...common}>
          <path d="M4 5h7v14H4z" />
          <path d="M13 5h7v14h-7z" />
          <path d="M4 19l8-2 8 2" />
          <line x1="6.5" y1="9" x2="9" y2="9" />
          <line x1="6.5" y1="12" x2="9" y2="12" />
          <line x1="15" y1="9" x2="17.5" y2="9" />
          <line x1="15" y1="12" x2="17.5" y2="12" />
        </svg>
      );
    case "whatsapp":
      return (
        <svg {...common}>
          <path d="M4.5 11.5a7 7 0 1 1 3.4 6L4 19l1.5-3.4a7 7 0 0 1-1-4.1z" />
          <path d="M9 10.5c.4 2 2.5 4 4.5 4.5l1-1.5a.7.7 0 0 1 .8-.3l1.7.6a.7.7 0 0 1 .5.7v1.4a.8.8 0 0 1-.8.8c-3.7-.1-7.3-3.7-7.4-7.4a.8.8 0 0 1 .8-.8h1.4a.7.7 0 0 1 .7.5l.6 1.7a.7.7 0 0 1-.3.8z" />
        </svg>
      );
    case "voiceNotes":
      return (
        <svg {...common}>
          <rect x="9.5" y="3" width="5" height="11" rx="2.5" />
          <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
          <line x1="12" y1="17.5" x2="12" y2="21" />
          <line x1="9" y1="21" x2="15" y2="21" />
        </svg>
      );
    case "phonePhotos":
      return (
        <svg {...common}>
          <rect x="3" y="5.5" width="18" height="13" rx="2" />
          <circle cx="8.5" cy="10" r="1.4" fill="currentColor" stroke="none" />
          <path d="M3.5 17l5-4.5 4 3.5 3-2.5 5 4" />
        </svg>
      );
    case "medical":
      return (
        <svg {...common}>
          <rect x="5" y="3.5" width="14" height="17" rx="2" />
          <line x1="12" y1="9" x2="12" y2="15" />
          <line x1="9" y1="12" x2="15" y2="12" />
        </svg>
      );
    case "bankSlips":
      return (
        <svg {...common}>
          <path d="M5 3.5h14v17l-2.5-1.5L14 20.5 12 19l-2 1.5-2.5-1.5L5 20.5z" />
          <line x1="8" y1="9" x2="16" y2="9" />
          <line x1="8" y1="12.5" x2="14" y2="12.5" />
          <line x1="8" y1="16" x2="12" y2="16" />
        </svg>
      );
    case "courtRecords":
      return (
        <svg {...common}>
          <path d="M5 9.5l5-5 9 9-2 2L8 6.5z" />
          <line x1="9" y1="13.5" x2="14.5" y2="19" />
          <line x1="3.5" y1="20.5" x2="20.5" y2="20.5" />
        </svg>
      );
    case "scannedPdfs":
      return (
        <svg {...common}>
          <path d="M6 3h9l4 4v14H6z" />
          <path d="M15 3v4h4" />
          <line x1="9" y1="13" x2="16" y2="13" />
          <line x1="9" y1="16.5" x2="14" y2="16.5" />
        </svg>
      );
    case "familyThreads":
      return (
        <svg {...common}>
          <path d="M4 6.5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-3 3v-3H6a2 2 0 0 1-2-2z" />
          <path d="M9 9.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1v3l-3-3" opacity="0.4" />
        </svg>
      );
    case "exif":
      return (
        <svg {...common}>
          <path d="M7 4l-3 3 3 3" />
          <path d="M17 4l3 3-3 3" />
          <line x1="10" y1="14" x2="10.01" y2="14" />
          <line x1="14" y1="14" x2="14.01" y2="14" />
          <line x1="10" y1="18" x2="10.01" y2="18" />
          <line x1="14" y1="18" x2="14.01" y2="18" />
          <line x1="6" y1="14" x2="6.01" y2="14" />
          <line x1="18" y1="14" x2="18.01" y2="14" />
        </svg>
      );
  }
}
