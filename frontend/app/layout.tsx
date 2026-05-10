import type { Metadata, Viewport } from "next";
import Image from "next/image";
import Link from "next/link";
import "./globals.css";
import { Toaster } from "@/components/toaster";
import { CommandPalette } from "@/components/command-palette";
import { DialogHost } from "@/components/dialog-host";
import { UserMenu } from "@/components/auth/user-menu";
import { PermissionsProvider } from "@/components/auth/permissions-provider";
import { ServiceWorkerRegistrar } from "@/components/service-worker-registrar";
import { MobileBottomNav } from "@/components/mobile-bottom-nav";
import { IntlProvider } from "@/lib/i18n/provider";
import { getMessages } from "@/lib/i18n/server";
import { RTL_LOCALES } from "@/lib/i18n/config";
import { format } from "@/lib/i18n/format";

export const metadata: Metadata = {
  title: "Verda — Codex-built litigation toolkits",
  description:
    "Verda turns a defender's messy case file into a deployable, case-specific litigation toolkit — in code, in Africa, one case at a time.",
  applicationName: "Verda",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Verda",
  },
  icons: {
    icon: "/verda-mark.svg",
    apple: "/verda-mark.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0a1429" },
    { media: "(prefers-color-scheme: dark)", color: "#0a1429" },
  ],
  width: "device-width",
  initialScale: 1,
  // Allow zoom for accessibility — keep the maximum modest so a stray
  // double-tap doesn't dump the user into 5×.
  maximumScale: 5,
  userScalable: true,
  viewportFit: "cover",
  colorScheme: "light",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { locale, messages, fallback } = await getMessages();
  const dir = RTL_LOCALES.has(locale) ? "rtl" : "ltr";
  const t = (key: string, vars?: Record<string, string | number>) =>
    format(messages, fallback, key, vars);

  return (
    <html lang={locale} dir={dir}>
      <body className="min-h-dvh bg-paper text-ink antialiased overflow-x-clip [touch-action:manipulation] [-webkit-tap-highlight-color:transparent] pb-[env(safe-area-inset-bottom)]">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[300] focus:rounded focus:bg-ink focus:px-3 focus:py-2 focus:text-paper"
        >
          {t("skipToContent")}
        </a>
        <IntlProvider locale={locale} messages={messages}>
          <PermissionsProvider>
            <div className="min-h-dvh flex flex-col">
              <SiteHeader t={t} />
              {/* pb-20 reserves room for the fixed mobile bottom-nav at the
                  viewport edge so content never hides behind it. md+ removes
                  the reservation since the bottom nav is hidden there. */}
              <main id="main" className="flex-1 pb-20 md:pb-0">{children}</main>
              <SiteFooter t={t} />
            </div>
            <CommandPalette />
            <DialogHost />
            <Toaster />
            <MobileBottomNav />
            <ServiceWorkerRegistrar />
          </PermissionsProvider>
        </IntlProvider>
      </body>
    </html>
  );
}

type T = (key: string, vars?: Record<string, string | number>) => string;

function SiteHeader({ t }: { t: T }) {
  return (
    <header className="sticky top-0 z-30 border-b border-paper-deep bg-paper/85 backdrop-blur-md pt-[env(safe-area-inset-top)]">
      <div className="app-shell flex items-center justify-between gap-2 py-2.5 sm:gap-4 sm:py-3">
        <Link href="/" className="flex items-center gap-2 focus-ring rounded shrink-0 min-w-0">
          <Image
            src="/verda-mark.svg"
            alt=""
            width={28}
            height={28}
            priority
            className="h-7 w-7 shrink-0"
          />
          <span className="text-base font-semibold tracking-tight">Verda</span>
          <span className="hidden md:inline text-[10px] uppercase tracking-[0.18em] text-ink/45">
            {t("header.tagline")}
          </span>
        </Link>
        <nav className="flex items-center gap-0.5 text-sm sm:gap-1">
          {/* The primary nav links are hidden on mobile — the bottom-nav
              tab bar carries them. md+ shows the desktop links again. */}
          <Link href="/cases" className="hidden md:inline-block rounded-md px-3 py-1.5 text-ink/70 hover:bg-ink/5 hover:text-ink focus-ring">
            {t("header.cases")}
          </Link>
          <Link href="/audit" className="hidden md:inline-block rounded-md px-3 py-1.5 text-ink/70 hover:bg-ink/5 hover:text-ink focus-ring">
            {t("header.audit")}
          </Link>
          <Link href="/about" className="hidden md:inline-block rounded-md px-3 py-1.5 text-ink/70 hover:bg-ink/5 hover:text-ink focus-ring">
            {t("header.about")}
          </Link>
          <span className="ml-2 hidden md:inline-flex items-center gap-1.5 rounded-md border border-ink/12 bg-paper-deep/60 px-2 py-1 text-[11px] text-ink/55">
            <span className="kbd">⌘</span><span className="kbd">K</span>
          </span>
          <UserMenu />
        </nav>
      </div>
    </header>
  );
}

function SiteFooter({ t }: { t: T }) {
  return (
    <footer className="hidden md:block mt-16 border-t border-paper-deep bg-paper text-ink/60 sm:mt-24">
      <div className="app-shell grid gap-6 py-8 sm:grid-cols-3 sm:py-10">
        <div>
          <div className="flex items-center gap-2">
            <Image
              src="/verda-mark.svg"
              alt=""
              width={24}
              height={24}
              className="h-6 w-6"
            />
            <span className="font-semibold text-ink">Verda</span>
          </div>
          <p className="mt-2 text-xs">{t("footer.blurb")}</p>
        </div>
        <div className="text-xs grid grid-cols-2 gap-1">
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-[0.18em] text-ink/40">{t("footer.product")}</p>
            <Link href="/cases" className="block hover:text-ink">{t("header.cases")}</Link>
            <Link href="/audit" className="block hover:text-ink">{t("footer.auditLog")}</Link>
            <Link href="/about" className="block hover:text-ink">{t("footer.architecture")}</Link>
          </div>
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-[0.18em] text-ink/40">{t("footer.trust")}</p>
            <span className="block">{t("footer.trustExports")}</span>
            <span className="block">{t("footer.trustHosted")}</span>
            <span className="block">{t("footer.trustViewer")}</span>
          </div>
        </div>
        <div className="text-xs sm:text-right">
          <p className="text-[10px] uppercase tracking-[0.18em] text-ink/40 sm:justify-end">{t("footer.builtFrom")}</p>
          <p className="mt-1">{t("footer.builtFromValue")}</p>
        </div>
      </div>
    </footer>
  );
}
