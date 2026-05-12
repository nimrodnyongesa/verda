"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * InfoTip — a small information-circle icon that surfaces a tooltip on
 * hover or focus.
 *
 * The tooltip is rendered through a React portal into <body> with
 * `position: fixed`, computed from the trigger's getBoundingClientRect.
 * That escapes every clipping ancestor (overflow:auto on tables,
 * overflow:hidden on cards, etc.) so the tooltip is never cut off when
 * it appears inside a scroll container.
 *
 * Tooltips close on scroll / resize rather than chasing the trigger,
 * which keeps the UI calm during page interaction.
 */

type Side = "top" | "right" | "bottom" | "left";

type Props = {
  content: React.ReactNode;
  side?: Side;
  className?: string;
  /** ARIA label for the icon button itself. Default: "More info". */
  label?: string;
  size?: "sm" | "md";
};

type Coords = { top: number; left: number; arrowSide: Side };

const TOOLTIP_GAP = 8;

export function InfoTip({
  content,
  side = "top",
  className = "",
  label = "More info",
  size = "sm",
}: Props) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<Coords | null>(null);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const closeTimer = useRef<number | null>(null);

  useEffect(() => {
    setMounted(true);
    return () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    };
  }, []);

  // Recompute position whenever the tooltip opens or its content size
  // changes. ResizeObserver picks up dynamic content (e.g. line-wrapping
  // when the side flips on viewport edge).
  useLayoutEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const tooltip = tooltipRef.current;
    if (!trigger || !tooltip) return;
    const place = () => {
      const r = trigger.getBoundingClientRect();
      const tr = tooltip.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let s: Side = side;

      // Auto-flip if the preferred side overflows the viewport.
      if (s === "top" && r.top - tr.height - TOOLTIP_GAP < 8) s = "bottom";
      else if (s === "bottom" && r.bottom + tr.height + TOOLTIP_GAP > vh - 8) s = "top";
      else if (s === "left" && r.left - tr.width - TOOLTIP_GAP < 8) s = "right";
      else if (s === "right" && r.right + tr.width + TOOLTIP_GAP > vw - 8) s = "left";

      let top = 0;
      let left = 0;
      switch (s) {
        case "top":
          top = r.top - tr.height - TOOLTIP_GAP;
          left = r.left + r.width / 2 - tr.width / 2;
          break;
        case "bottom":
          top = r.bottom + TOOLTIP_GAP;
          left = r.left + r.width / 2 - tr.width / 2;
          break;
        case "left":
          top = r.top + r.height / 2 - tr.height / 2;
          left = r.left - tr.width - TOOLTIP_GAP;
          break;
        case "right":
          top = r.top + r.height / 2 - tr.height / 2;
          left = r.right + TOOLTIP_GAP;
          break;
      }
      // Clamp inside the viewport with an 8 px margin so the tooltip
      // doesn't bleed off-screen on small windows.
      left = Math.max(8, Math.min(vw - tr.width - 8, left));
      top = Math.max(8, Math.min(vh - tr.height - 8, top));
      setCoords({ top, left, arrowSide: s });
    };
    place();

    const obs = new ResizeObserver(place);
    obs.observe(tooltip);
    return () => obs.disconnect();
  }, [open, side]);

  // Close on scroll/resize so the tooltip never floats away from its
  // trigger while the page moves.
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  const handleEnter = () => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    setOpen(true);
  };
  const handleLeave = () => {
    closeTimer.current = window.setTimeout(() => setOpen(false), 80);
  };

  const dim = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";

  return (
    <span
      className={"relative inline-flex items-center align-middle " + className}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        className="inline-flex items-center justify-center rounded-full text-ink/45 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/50"
        tabIndex={0}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={dim}
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <line x1="12" y1="11" x2="12" y2="16.5" />
          <circle cx="12" cy="8" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      </button>
      {mounted && open
        ? createPortal(
            <div
              ref={tooltipRef}
              role="tooltip"
              onMouseEnter={handleEnter}
              onMouseLeave={handleLeave}
              style={{
                position: "fixed",
                top: coords?.top ?? -9999,
                left: coords?.left ?? -9999,
                background: "var(--color-paper)",
                visibility: coords ? "visible" : "hidden",
              }}
              className="pointer-events-auto z-[300] min-w-[170px] max-w-[230px] rounded-md border border-ink/15 px-3 py-2 text-[12px] leading-relaxed text-ink shadow-[0_18px_36px_-18px_rgba(10,20,41,0.45)]"
            >
              {content}
              {coords ? (
                <span
                  aria-hidden="true"
                  className={
                    "absolute h-2 w-2 rotate-45 " + arrowPosition(coords.arrowSide)
                  }
                  style={{
                    background: "var(--color-paper)",
                    border: "1px solid rgba(10,20,41,0.15)",
                    borderTopColor:
                      coords.arrowSide === "bottom" ? "rgba(10,20,41,0.15)" : "transparent",
                    borderLeftColor:
                      coords.arrowSide === "right" ? "rgba(10,20,41,0.15)" : "transparent",
                    borderRightColor:
                      coords.arrowSide === "left" ? "rgba(10,20,41,0.15)" : "transparent",
                    borderBottomColor:
                      coords.arrowSide === "top" ? "rgba(10,20,41,0.15)" : "transparent",
                  }}
                />
              ) : null}
            </div>,
            document.body
          )
        : null}
    </span>
  );
}

function arrowPosition(side: Side): string {
  switch (side) {
    case "right":
      return "left-[-4px] top-1/2 -translate-y-1/2";
    case "bottom":
      return "top-[-4px] left-1/2 -translate-x-1/2";
    case "left":
      return "right-[-4px] top-1/2 -translate-y-1/2";
    case "top":
    default:
      return "bottom-[-4px] left-1/2 -translate-x-1/2";
  }
}
