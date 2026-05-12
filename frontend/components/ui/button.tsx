"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

const styles: Record<Variant, string> = {
  primary:
    "bg-ink text-paper hover:bg-ink-soft border-ink shadow-[0_8px_24px_-12px_rgba(10,20,41,.5)]",
  secondary:
    "bg-gold text-ink hover:bg-gold-bright border-gold shadow-[0_8px_24px_-12px_rgba(212,165,52,.7)]",
  ghost:
    "bg-transparent text-ink hover:bg-ink/[.06] border-transparent",
  outline:
    "bg-transparent text-ink hover:bg-ink/[.04] border-ink/15",
  danger:
    "bg-rust text-paper hover:bg-rust/85 border-rust",
};

// Sizes carry tap-target floor (≥40px high on sm, ≥44px on md/lg) so
// every Button respects the iOS / Android touch-size guidance.
const sizes: Record<Size, string> = {
  sm: "min-h-[40px] px-3 py-2 text-xs gap-1.5",
  md: "min-h-[44px] px-4 py-2.5 text-sm gap-2",
  lg: "min-h-[48px] px-5 py-3 text-base gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }>(
  function Button({ variant = "primary", size = "md", className = "", ...props }, ref) {
    return (
      <button
        ref={ref}
        {...props}
        className={
          "inline-flex shrink-0 flex-row flex-nowrap items-center justify-center whitespace-nowrap rounded-lg border font-medium transition focus-ring active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60 " +
          styles[variant] + " " + sizes[size] + " " + className
        }
      />
    );
  }
);
