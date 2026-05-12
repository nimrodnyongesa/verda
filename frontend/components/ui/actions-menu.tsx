"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ActionItem = {
  key: string;
  label: string;
  /** Optional left-side icon (any React node — usually an inline SVG). */
  icon?: React.ReactNode;
  onSelect: () => void;
  /** Render the item disabled. Pair with `disabledHint` for the why. */
  disabled?: boolean;
  /** Tooltip / title surfaced when disabled. */
  disabledHint?: string;
  /** Render the item in the destructive (rust) tone. */
  danger?: boolean;
  /** Visual separator after this item. */
  divider?: boolean;
};

/**
 * ActionsMenu — a compact vertical-ellipsis dropdown.
 *
 * The popover renders through a React portal into <body> with
 * `position: fixed`, so it escapes any clipping ancestor (overflow:auto
 * tables, overflow:hidden cards). Position is computed from the trigger
 * button's getBoundingClientRect; if the menu would overflow the
 * viewport bottom it flips above the trigger.
 *
 * Closes on outside-click, Esc, scroll, and resize.
 */
export function ActionsMenu({
  items,
  align = "right",
  buttonLabel = "Actions",
  className = "",
}: {
  items: ActionItem[];
  align?: "right" | "left";
  buttonLabel?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Compute fixed-position coordinates whenever the menu opens or its
  // size changes (longer label can grow the menu height; flip up if so).
  useLayoutEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const menu = menuRef.current;
    if (!trigger || !menu) return;
    const place = () => {
      const r = trigger.getBoundingClientRect();
      const mr = menu.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = mr.width;
      const height = mr.height;

      const wantsAbove = r.bottom + height + 6 > vh - 8;
      const top = wantsAbove ? r.top - height - 6 : r.bottom + 6;
      let left = align === "right" ? r.right - width : r.left;
      // Clamp inside the viewport with an 8 px margin.
      left = Math.max(8, Math.min(vw - width - 8, left));
      setCoords({ top, left, width });
    };
    place();

    const obs = new ResizeObserver(place);
    obs.observe(menu);
    return () => obs.disconnect();
  }, [open, align]);

  // Close on outside click / Esc / scroll / resize.
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!triggerRef.current?.contains(t) && !menuRef.current?.contains(t)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const close = () => setOpen(false);
    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <span className={"relative inline-flex " + className}>
      <button
        ref={triggerRef}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={buttonLabel}
        className="grid h-7 w-7 place-items-center rounded-full bg-transparent p-0 text-ink/45 transition hover:bg-ink/5 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/45"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
          <circle cx="12" cy="5" r="1.6" />
          <circle cx="12" cy="12" r="1.6" />
          <circle cx="12" cy="19" r="1.6" />
        </svg>
      </button>
      {mounted && open
        ? createPortal(
            <div
              ref={menuRef}
              role="menu"
              style={{
                position: "fixed",
                top: coords?.top ?? -9999,
                left: coords?.left ?? -9999,
                visibility: coords ? "visible" : "hidden",
              }}
              className="z-[300] w-52 overflow-hidden rounded-lg border border-ink/10 bg-white shadow-2xl shadow-ink/20"
              onClick={(e) => e.stopPropagation()}
            >
              <ul className="py-0.5">
                {items.map((item) => (
                  <li key={item.key}>
                    <button
                      role="menuitem"
                      disabled={item.disabled}
                      title={item.disabled ? item.disabledHint : undefined}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (item.disabled) return;
                        setOpen(false);
                        item.onSelect();
                      }}
                      className={
                        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] leading-snug transition " +
                        (item.disabled
                          ? "cursor-not-allowed text-ink/30"
                          : item.danger
                          ? "text-rust hover:bg-rust/8"
                          : "text-ink/85 hover:bg-paper-deep/60 hover:text-ink")
                      }
                    >
                      <span
                        aria-hidden="true"
                        className={
                          "grid h-4 w-4 shrink-0 place-items-center " +
                          (item.disabled
                            ? "text-ink/25"
                            : item.danger
                            ? "text-rust"
                            : "text-ink/55")
                        }
                      >
                        {item.icon ?? <DotIcon />}
                      </span>
                      <span className="flex-1 truncate">{item.label}</span>
                    </button>
                    {item.divider ? (
                      <div aria-hidden="true" className="my-0.5 border-t border-ink/8" />
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>,
            document.body
          )
        : null}
    </span>
  );
}

function DotIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-1.5 w-1.5" aria-hidden="true">
      <circle cx="12" cy="12" r="2.4" />
    </svg>
  );
}
