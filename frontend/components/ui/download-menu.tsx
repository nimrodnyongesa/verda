"use client";

import { useEffect, useRef, useState } from "react";

/**
 * DownloadMenu — single primary button with a dropdown chevron.
 *
 * Click opens a popover listing the format options. The first option is
 * the primary action surfaced on the button label so the user always sees
 * what a *single* click would do; the chevron opens the menu when they
 * want a different format.
 *
 * Built to be embedded next to artefacts (petition, drafted motions) in
 * the workspace panels. The component is presentation-only — it does not
 * fetch anything itself; ``onSelect(option.key)`` is the caller's hook.
 */

export type DownloadOption = {
  key: string;
  label: string;
  description?: string;
  /** Inline icon (any React node — usually an SVG). */
  icon?: React.ReactNode;
};

export function DownloadMenu({
  label = "Download",
  options,
  onSelect,
  busy = false,
  align = "right",
  primaryKey,
}: {
  label?: string;
  options: DownloadOption[];
  onSelect: (key: string) => void;
  busy?: boolean;
  align?: "left" | "right";
  primaryKey?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const primary = options.find((o) => o.key === primaryKey) ?? options[0];

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        disabled={busy || !primary}
        onClick={(e) => {
          e.preventDefault();
          if (!primary) return;
          onSelect(primary.key);
        }}
        className="inline-flex items-center gap-1.5 rounded-l-md border border-ink/12 border-r-0 bg-white px-3 py-1.5 text-xs font-medium text-ink/80 transition hover:border-gold hover:text-ink disabled:cursor-not-allowed disabled:text-ink/35"
      >
        <DownloadIcon />
        {busy ? "Building…" : `${label} · ${primary?.label ?? "—"}`}
      </button>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="More export options"
        disabled={busy}
        onClick={(e) => {
          e.preventDefault();
          setOpen((o) => !o);
        }}
        className="inline-flex items-center justify-center rounded-r-md border border-ink/12 bg-white px-2 py-1.5 text-ink/65 transition hover:border-gold hover:text-ink disabled:cursor-not-allowed disabled:text-ink/35"
      >
        <ChevronIcon open={open} />
      </button>
      {open ? (
        <div
          role="menu"
          className={
            "absolute top-full z-40 mt-1 w-72 overflow-hidden rounded-lg border border-ink/10 bg-white shadow-xl shadow-ink/15 " +
            (align === "right" ? "right-0" : "left-0")
          }
        >
          <ul className="py-1">
            {options.map((o) => (
              <li key={o.key}>
                <button
                  role="menuitem"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setOpen(false);
                    onSelect(o.key);
                  }}
                  className="flex w-full items-start gap-3 px-3 py-2.5 text-left text-sm transition hover:bg-paper-deep/60"
                >
                  <span aria-hidden="true" className="mt-0.5 grid h-5 w-5 place-items-center text-ink/55">
                    {o.icon ?? <DownloadIcon className="h-4 w-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-ink">{o.label}</span>
                    {o.description ? (
                      <span className="block text-[11px] text-ink/55">{o.description}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function DownloadIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 4v12" />
      <path d="m6 12 6 6 6-6" />
      <path d="M5 21h14" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={"h-3 w-3 transition-transform " + (open ? "rotate-180" : "")} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
