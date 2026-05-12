/**
 * DateText — a single rendering helper for every date / timestamp in the app.
 *
 * Centralises three things the UI used to do ad-hoc per page:
 *   1. Parse safely — `new Date("")` and `new Date(undefined)` both produce
 *      "Invalid Date" without throwing, so we explicitly check getTime().
 *   2. Format with the user's locale.
 *   3. Mark the result with the `.date-text` class (dotted underline) so
 *      machine-formatted dates are visually distinct from prose.
 *
 * Pass either `iso` (ISO string from the server) or `value` (a Date instance)
 * plus an optional `variant` to control the formatter.
 */

import type { ReactNode } from "react";

type Variant = "datetime" | "date" | "time" | "relative";

type Props = {
  iso?: string | null;
  value?: Date | null;
  variant?: Variant;
  emptyFallback?: ReactNode;
  title?: string;
  className?: string;
};

function format(d: Date, variant: Variant): string {
  switch (variant) {
    case "date":
      return d.toLocaleDateString(undefined, { dateStyle: "medium" });
    case "time":
      return d.toLocaleTimeString(undefined, { timeStyle: "short" });
    case "relative":
      return relative(d);
    case "datetime":
    default:
      return d.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
  }
}

function relative(d: Date): string {
  const diff = Date.now() - d.getTime();
  const sec = Math.round(diff / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (Math.abs(sec) < 60) return "just now";
  if (Math.abs(min) < 60) return `${min}m ago`;
  if (Math.abs(hr) < 24) return `${hr}h ago`;
  if (Math.abs(day) < 30) return `${day}d ago`;
  return d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function DateText({
  iso,
  value,
  variant = "datetime",
  emptyFallback = "—",
  title,
  className = "",
}: Props) {
  const d = value ?? (iso ? new Date(iso) : null);
  if (!d || Number.isNaN(d.getTime())) {
    return (
      <span className={"text-ink/45 " + className} title={title}>
        {emptyFallback}
      </span>
    );
  }
  const formatted = format(d, variant);
  // The full ISO is exposed via `title` for power users hovering on a row.
  const tooltip = title ?? d.toISOString();
  return (
    <span className={"date-text text-ink/65 " + className} title={tooltip}>
      {formatted}
    </span>
  );
}
