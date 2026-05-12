"use client";

import { useId } from "react";

type Props = {
  className?: string;
  cell?: number;
  strokeOpacity?: number;
};

export function AnimatedGrid({ className = "", cell = 64, strokeOpacity = 0.16 }: Props) {
  const id = useId().replace(/[^a-z0-9]/gi, "");
  return (
    <svg
      aria-hidden
      className={"pointer-events-none absolute inset-0 h-full w-full " + className}
    >
      <defs>
        <pattern id={`g-${id}`} width={cell} height={cell} patternUnits="userSpaceOnUse">
          <path
            d={`M ${cell} 0 L 0 0 0 ${cell}`}
            fill="none"
            stroke="currentColor"
            strokeOpacity={strokeOpacity}
            strokeWidth="1"
          />
        </pattern>
        <radialGradient id={`m-${id}`} cx="50%" cy="35%" r="70%">
          <stop offset="0" stopColor="white" stopOpacity="1" />
          <stop offset="1" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id={`mk-${id}`}>
          <rect width="100%" height="100%" fill={`url(#m-${id})`} />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill={`url(#g-${id})`} mask={`url(#mk-${id})`} />
      <g mask={`url(#mk-${id})`}>
        {[0, 1, 2].map((i) => (
          <rect
            key={i}
            width={cell}
            height={cell}
            x={(i + 1) * cell * 3}
            y={(i + 2) * cell * 2}
            fill="rgba(240,193,75,0.18)"
            style={{
              animation: `wk-grid-pulse 4s ease-in-out ${i * 0.6}s infinite`,
            }}
          />
        ))}
      </g>
      <style>{`
        @keyframes wk-grid-pulse {
          0%, 100% { opacity: 0; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-4px); }
        }
        @media (prefers-reduced-motion: reduce) {
          rect { animation: none !important; }
        }
      `}</style>
    </svg>
  );
}
