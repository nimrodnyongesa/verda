import { ReactNode } from "react";

type Props = {
  children: ReactNode;
  durationSec?: number;
  className?: string;
  reverse?: boolean;
  pauseOnHover?: boolean;
};

export function Marquee({
  children,
  durationSec = 30,
  className = "",
  reverse = false,
  pauseOnHover = true,
}: Props) {
  return (
    <div
      className={
        "wk-marquee group/marquee relative flex overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)] " +
        className
      }
    >
      <div className="wk-marquee__track flex shrink-0 items-center gap-6 pr-6">{children}</div>
      <div aria-hidden className="wk-marquee__track flex shrink-0 items-center gap-6 pr-6">
        {children}
      </div>
      <style>{`
        .wk-marquee__track {
          animation: wk-marquee-scroll ${durationSec}s linear infinite;
          animation-direction: ${reverse ? "reverse" : "normal"};
        }
        ${
          pauseOnHover
            ? ".wk-marquee:hover .wk-marquee__track { animation-play-state: paused; }"
            : ""
        }
        @keyframes wk-marquee-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-100%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .wk-marquee__track { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
