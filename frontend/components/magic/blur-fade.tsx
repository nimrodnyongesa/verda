"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

type Props = {
  children: ReactNode;
  delay?: number;
  duration?: number;
  yOffset?: number;
  className?: string;
  once?: boolean;
};

export function BlurFade({
  children,
  delay = 0,
  duration = 600,
  yOffset = 16,
  className = "",
  once = true,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setVisible(true);
      return;
    }
    const node = ref.current;
    if (!node) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setVisible(true);
            if (once) obs.disconnect();
          } else if (!once) {
            setVisible(false);
          }
        }
      },
      { threshold: 0.1 }
    );
    obs.observe(node);
    return () => obs.disconnect();
  }, [once]);

  const style: React.CSSProperties = {
    transition: `opacity ${duration}ms cubic-bezier(.2,.7,.3,1) ${delay}ms, transform ${duration}ms cubic-bezier(.2,.7,.3,1) ${delay}ms, filter ${duration}ms ease ${delay}ms`,
    opacity: visible ? 1 : 0,
    transform: visible ? "translateY(0)" : `translateY(${yOffset}px)`,
    filter: visible ? "blur(0)" : "blur(6px)",
    willChange: "opacity, transform, filter",
  };

  return (
    <div ref={ref} style={style} className={className}>
      {children}
    </div>
  );
}
