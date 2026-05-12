import Link from "next/link";
import { AUTH_ENABLED, PROVIDERS } from "@/lib/auth/config";
import { AnimatedGrid } from "@/components/magic/animated-grid";
import { DotPattern } from "@/components/magic/dot-pattern";
import { BlurFade } from "@/components/magic/blur-fade";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export const dynamic = "force-dynamic";

const PROVIDER_GLYPH: Record<string, string> = {
  keycloak: "K",
  auth0: "A0",
  authentik: "A",
  azure: "M",
  google: "G",
  okta: "O",
  github: "GH",
};

const DEMO_USERS = [
  { user: "advocate", pass: "advocate", role: "lawyer" },
  { user: "paralegal", pass: "paralegal", role: "paralegal" },
  { user: "nimrod", pass: "nimrod", role: "admin · lawyer" },
];

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string; error?: string }>;
}) {
  const sp = await searchParams;
  const returnTo = sp?.returnTo ?? "/";
  const error = sp?.error ?? null;
  const { messages, fallback } = await getMessages();
  const t = (key: string, vars?: Record<string, string | number>) =>
    format(messages, fallback, key, vars);

  if (!AUTH_ENABLED) {
    // The localised body has interpolated env-var / command tokens we want
    // to render as <code>. Split on the literal token strings and inject
    // styled spans where the placeholders landed.
    const tokens = {
      frontendVar: "NEXT_PUBLIC_WAKILI_AUTH_ENABLED=true",
      backendVar: "WAKILI_AUTH_ENABLED=true",
      makeCmd: "make keycloak",
    };
    const body = t("signIn.authDisabledBody", tokens);
    const re = new RegExp(
      `(${[tokens.frontendVar, tokens.backendVar, tokens.makeCmd]
        .map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|")})`,
    );
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 grid gap-4">
        <h1 className="serif text-3xl font-bold tracking-tight">{t("signIn.authDisabled")}</h1>
        <p className="text-sm text-ink/70 leading-relaxed">
          {body.split(re).map((seg, i) =>
            seg === tokens.frontendVar ||
            seg === tokens.backendVar ||
            seg === tokens.makeCmd ? (
              <code key={i} className="mono">{seg}</code>
            ) : (
              <span key={i}>{seg}</span>
            ),
          )}
        </p>
        <Link href="/" className="text-sm text-ink/60 underline-offset-2 hover:underline">
          {t("signIn.backHome")}
        </Link>
      </div>
    );
  }

  return (
    <div className="relative isolate min-h-[calc(100dvh-180px)] overflow-hidden">
      {/* Background — matches the home hero */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-ink via-ink to-ink-deeper" aria-hidden />
      <div className="absolute inset-0 -z-10 text-paper/25" aria-hidden>
        <AnimatedGrid />
      </div>
      <div className="absolute inset-0 -z-10 text-gold/35" aria-hidden>
        <DotPattern size={26} dot={1} />
      </div>
      <div className="absolute inset-x-0 bottom-0 -z-10 h-32 bg-gradient-to-b from-transparent to-paper" aria-hidden />

      <div className="mx-auto grid max-w-md gap-6 px-4 py-12 sm:px-6 sm:py-16">
        <BlurFade>
          <header className="grid gap-3 text-paper">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-gold/35 bg-paper/5 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-gold">
              <Lock />
              {t("signIn.continue")}
            </span>
            <h1 className="serif text-3xl font-bold leading-tight tracking-tight balanced sm:text-4xl">
              {t("signIn.title")}
            </h1>
            <p className="text-sm text-paper/75">{t("signIn.subtitle")}</p>
          </header>
        </BlurFade>

        {error ? (
          <BlurFade delay={60}>
            <div
              role="alert"
              className="rounded-xl border border-rust/45 bg-rust/15 px-4 py-3 text-sm text-paper backdrop-blur"
            >
              <p className="font-semibold text-rust">{t("signIn.errorTitle")}</p>
              <p className="mt-1 break-words text-paper/85 [overflow-wrap:anywhere]">
                {decodeURIComponent(error)}
              </p>
              <p className="mt-2 text-[11px] text-paper/55">
                {t("signIn.errorHint", {
                  resetCmd: "make stack-reset",
                  statusCmd: "make auth-status",
                })
                  .split(/(make stack-reset|make auth-status)/)
                  .map((seg, i) =>
                    seg === "make stack-reset" || seg === "make auth-status" ? (
                      <code key={i} className="mono">{seg}</code>
                    ) : (
                      <span key={i}>{seg}</span>
                    ),
                  )}
              </p>
            </div>
          </BlurFade>
        ) : null}

        <BlurFade delay={120}>
          <ul className="grid gap-2.5">
            {PROVIDERS.map((p) => {
              const glyph = PROVIDER_GLYPH[p.id] ?? p.name.slice(0, 1).toUpperCase();
              return (
                <li key={p.id}>
                  <a
                    href={`/api/auth/login?provider=${encodeURIComponent(p.id)}&returnTo=${encodeURIComponent(returnTo)}`}
                    className="group relative flex flex-row flex-nowrap items-center gap-3 overflow-hidden rounded-2xl border border-paper/12 bg-paper/[0.06] p-3 backdrop-blur-md transition hover:border-gold/55 hover:bg-paper/[0.1] focus-ring sm:p-4"
                  >
                    <span
                      aria-hidden
                      className="absolute inset-0 -translate-x-full bg-[linear-gradient(115deg,transparent_30%,rgba(240,193,75,0.18)_50%,transparent_70%)] transition-transform duration-700 group-hover:translate-x-full"
                    />
                    <span
                      aria-hidden
                      className="relative grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-gold/30 bg-gradient-to-br from-gold/30 to-gold/10 text-base font-bold text-paper"
                    >
                      {glyph}
                    </span>
                    <span className="relative flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="text-sm font-semibold text-paper sm:text-base">
                        {t("signIn.providerCta", { provider: p.name })}
                      </span>
                      {p.description ? (
                        <span className="line-clamp-1 text-[11px] text-paper/60 sm:text-xs">
                          {p.description}
                        </span>
                      ) : null}
                      <span className="mono truncate text-[10px] text-paper/35 sm:text-[11px]">
                        {p.issuer}
                      </span>
                    </span>
                    <span
                      aria-hidden
                      className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full border border-paper/15 bg-paper/10 text-paper transition group-hover:border-gold group-hover:bg-gold group-hover:text-ink"
                    >
                      →
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        </BlurFade>

        <BlurFade delay={200}>
          <details className="rounded-xl border border-paper/15 bg-paper-deep/95 p-4 text-ink backdrop-blur-md">
            <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-semibold">
              <span>{t("signIn.demoCreds")}</span>
              <span aria-hidden className="text-ink/40">▾</span>
            </summary>
            <p className="mt-2 text-xs text-ink/65">
              {t("signIn.demoBody", { makeCmd: "make stack" })
                .split(/(make stack)/)
                .map((seg, i) =>
                  seg === "make stack" ? (
                    <code key={i} className="mono">{seg}</code>
                  ) : (
                    <span key={i}>{seg}</span>
                  ),
                )}
            </p>
            <ul className="mt-3 grid gap-1.5 text-xs">
              {DEMO_USERS.map((u) => (
                <li
                  key={u.user}
                  className="grid grid-cols-[auto_auto_1fr] items-center gap-x-2 gap-y-0 rounded-lg border border-ink/8 bg-white px-2.5 py-1.5"
                >
                  <span className="mono font-semibold">{u.user}</span>
                  <span className="mono text-ink/45">/</span>
                  <span className="mono">{u.pass}</span>
                  <span className="col-span-3 mt-0.5 text-[10px] uppercase tracking-[0.14em] text-ink/45">
                    {t("signIn.demoRole", { role: u.role })}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        </BlurFade>

        <BlurFade delay={260}>
          <p className="text-center text-[11px] text-paper/55">
            {t("signIn.footer")}
            <br />
            {t("signIn.footerExtra", { file: "frontend/lib/auth/config.ts" })
              .split(/(frontend\/lib\/auth\/config\.ts)/)
              .map((seg, i) =>
                seg === "frontend/lib/auth/config.ts" ? (
                  <code key={i} className="mono">{seg}</code>
                ) : (
                  <span key={i}>{seg}</span>
                ),
              )}
          </p>
        </BlurFade>
      </div>
    </div>
  );
}

function Lock() {
  return (
    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4.5" y="10" width="15" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 1 1 8 0v3" />
    </svg>
  );
}
