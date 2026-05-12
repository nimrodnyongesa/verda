"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  shimmerColor?: string;
  background?: string;
};

export const ShimmerButton = forwardRef<HTMLButtonElement, Props>(
  function ShimmerButton(
    { shimmerColor = "rgba(240,193,75,.85)", background = "var(--color-ink)", className = "", style, children, ...rest },
    ref
  ) {
    return (
      <button
        ref={ref}
        {...rest}
        className={
          "wk-shimmer relative inline-flex shrink-0 flex-row flex-nowrap items-center justify-center gap-2 overflow-hidden whitespace-nowrap rounded-full px-6 py-3 text-sm font-medium text-paper transition-transform active:scale-[.98] min-h-[44px] " +
          className
        }
        style={{
          background,
          boxShadow:
            "0 0 0 1px rgba(212,165,52,.5), 0 8px 30px -8px rgba(212,165,52,.45)",
          ...style,
        }}
      >
        <span
          aria-hidden
          className="wk-shimmer__layer"
          style={{
            background:
              `linear-gradient(115deg, transparent 35%, ${shimmerColor} 50%, transparent 65%)`,
          }}
        />
        <span className="relative z-[1] inline-flex items-center gap-2">{children}</span>
        <style jsx>{`
          .wk-shimmer__layer {
            position: absolute;
            inset: 0;
            transform: translateX(-120%);
            opacity: 0;
            transition: opacity 200ms ease;
            pointer-events: none;
          }
          .wk-shimmer:hover .wk-shimmer__layer,
          .wk-shimmer:focus-visible .wk-shimmer__layer {
            opacity: 1;
            animation: wk-shimmer-slide 1.6s linear infinite;
          }
          @keyframes wk-shimmer-slide {
            0% { transform: translateX(-120%); }
            100% { transform: translateX(120%); }
          }
          @media (prefers-reduced-motion: reduce) {
            .wk-shimmer__layer { animation: none !important; }
          }
        `}</style>
      </button>
    );
  }
);
