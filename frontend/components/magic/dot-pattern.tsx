type Props = {
  size?: number;
  dot?: number;
  className?: string;
  fade?: boolean;
};

export function DotPattern({ size = 18, dot = 1.2, className = "", fade = true }: Props) {
  const id = `dp-${size}-${dot}`;
  return (
    <svg
      aria-hidden
      className={"pointer-events-none absolute inset-0 h-full w-full " + className}
    >
      <defs>
        <pattern id={id} x="0" y="0" width={size} height={size} patternUnits="userSpaceOnUse">
          <circle cx={size / 2} cy={size / 2} r={dot} fill="currentColor" />
        </pattern>
        {fade ? (
          <radialGradient id={`${id}-mask`} cx="50%" cy="40%" r="65%">
            <stop offset="0" stopColor="white" stopOpacity="1" />
            <stop offset="1" stopColor="white" stopOpacity="0" />
          </radialGradient>
        ) : null}
        {fade ? (
          <mask id={`${id}-m`}>
            <rect width="100%" height="100%" fill={`url(#${id}-mask)`} />
          </mask>
        ) : null}
      </defs>
      <rect
        width="100%"
        height="100%"
        fill={`url(#${id})`}
        mask={fade ? `url(#${id}-m)` : undefined}
      />
    </svg>
  );
}
