"use client";

import { useEffect, useRef } from "react";

type Props = {
  className?: string;
  density?: number;
  color?: string;
};

export function Sparkles({ className = "", density = 32, color = "#f0c14b" }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (typeof window === "undefined") return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0, h = 0;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    type Particle = { x: number; y: number; r: number; o: number; v: number; t: number };
    const particles: Particle[] = [];
    for (let i = 0; i < density; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.4 + 0.4,
        o: Math.random() * 0.6 + 0.2,
        v: Math.random() * 0.4 + 0.1,
        t: Math.random() * Math.PI * 2,
      });
    }

    let raf = 0;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color;
      for (const p of particles) {
        p.t += p.v * 0.02;
        const o = (Math.sin(p.t) * 0.5 + 0.5) * p.o;
        ctx.globalAlpha = o;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [density, color]);

  return <canvas ref={ref} aria-hidden className={"pointer-events-none absolute inset-0 h-full w-full " + className} />;
}
