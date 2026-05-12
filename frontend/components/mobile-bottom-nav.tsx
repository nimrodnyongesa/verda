"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/lib/i18n/provider";

/**
 * MobileBottomNav — iOS / Android-style tab bar.
 *
 * Visible only on screens narrower than the `md` breakpoint (≤ 767 px).
 * The desktop top header carries the same primary navigation, so on
 * tablet and up this component disappears and the page content takes
 * back the full height it would have given to a fixed bottom bar.
 *
 * Active route is computed from `usePathname` so the highlight survives
 * client-side navigation. The active tab gets a 2-px gold underline at
 * the *top* of the bar (touching the page divider) which is the pattern
 * iOS / Material both use to show "you are here" without a heavy fill.
 */

type Tab = {
  href: string;
  /** Catalog key — resolved via the active locale's catalog at render. */
  labelKey: string;
  icon: React.ReactNode;
};

const TABS: Tab[] = [
  { href: "/", labelKey: "bottomNav.home", icon: <HomeIcon /> },
  { href: "/cases", labelKey: "bottomNav.cases", icon: <FoldersIcon /> },
  { href: "/audit", labelKey: "bottomNav.audit", icon: <AuditIcon /> },
  { href: "/profile", labelKey: "bottomNav.me", icon: <UserIcon /> },
];

export function MobileBottomNav() {
  const t = useT();
  const pathname = usePathname() ?? "/";
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <nav
      role="navigation"
      aria-label="Primary"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 border-t border-ink/10 bg-paper/95 backdrop-blur pb-[env(safe-area-inset-bottom,0px)] shadow-[0_-12px_40px_-20px_rgba(10,20,41,0.25)]"
    >
      <ul className="grid grid-cols-4">
        {TABS.map((tab) => {
          const active = isActive(tab.href);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={
                  "relative flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-medium uppercase tracking-[0.12em] transition " +
                  (active ? "text-ink" : "text-ink/55 hover:text-ink/80")
                }
              >
                {active ? (
                  <span
                    aria-hidden="true"
                    className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-10 rounded-b-full bg-gold"
                  />
                ) : null}
                <span className={active ? "text-ink" : "text-ink/55"}>{tab.icon}</span>
                <span>{t(tab.labelKey)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Icons — outline SVGs sized for the bottom nav (h-5 w-5, 1.7 stroke).
// ---------------------------------------------------------------------------

const iconCls = "h-5 w-5";
const iconBase = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  className: iconCls,
  "aria-hidden": true,
};

function HomeIcon() {
  return (
    <svg {...iconBase}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9.5" />
    </svg>
  );
}
function FoldersIcon() {
  return (
    <svg {...iconBase}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function AuditIcon() {
  return (
    <svg {...iconBase}>
      <path d="M5 3h11l4 4v14H5z" />
      <path d="M15 3v4h4" />
      <line x1="9" y1="11" x2="17" y2="11" />
      <line x1="9" y1="15" x2="17" y2="15" />
      <line x1="9" y1="19" x2="13" y2="19" />
    </svg>
  );
}
function UserIcon() {
  return (
    <svg {...iconBase}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}
