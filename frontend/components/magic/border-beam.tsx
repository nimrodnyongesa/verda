type Props = {
  duration?: number;
  delay?: number;
  className?: string;
  colorFrom?: string;
  colorTo?: string;
};

export function BorderBeam({
  duration = 9,
  delay = 0,
  className = "",
  colorFrom = "#f0c14b",
  colorTo = "#d4a534",
}: Props) {
  return (
    <div
      aria-hidden
      className={"pointer-events-none absolute inset-0 rounded-[inherit] [mask:linear-gradient(white,white)_content-box,linear-gradient(white,white)] [mask-composite:exclude] [mask-clip:padding-box,border-box] " + className}
      style={{
        padding: 1,
      }}
    >
      <div
        className="wk-bb absolute inset-0 rounded-[inherit]"
        style={{
          background: `conic-gradient(from 90deg at 50% 50%, transparent 0deg, ${colorFrom} 30deg, ${colorTo} 60deg, transparent 90deg)`,
          animation: `wk-bb-spin ${duration}s linear ${delay}s infinite`,
        }}
      />
      <style>{`
        @keyframes wk-bb-spin {
          to { transform: rotate(360deg); }
        }
        @media (prefers-reduced-motion: reduce) {
          .wk-bb { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
