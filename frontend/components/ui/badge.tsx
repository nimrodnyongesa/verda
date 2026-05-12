import { ReactNode } from "react";

const variants = {
  gold: "bg-gold-soft/60 text-ink border-gold/40",
  ink: "bg-ink text-paper border-ink",
  paper: "bg-paper-deep text-ink border-ink/12",
  fern: "bg-fern/12 text-fern border-fern/30",
  rust: "bg-rust/12 text-rust border-rust/30",
  outline: "bg-transparent text-ink/70 border-ink/18",
  dot: "bg-transparent text-ink/70 border-transparent",
} as const;

export function Badge({
  children,
  variant = "gold",
  className = "",
}: {
  children: ReactNode;
  variant?: keyof typeof variants;
  className?: string;
}) {
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.08em] " +
        variants[variant] + " " + className
      }
    >
      {children}
    </span>
  );
}
