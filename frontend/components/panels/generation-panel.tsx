"use client";

import { useEffect, useMemo, useState } from "react";
import type { GenerationEvent, GenerationRun } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardBody } from "../ui/card";
import { EmptyState } from "../ui/empty-state";
import { NumberTicker } from "../magic/number-ticker";

const ACTOR_TONE: Record<string, string> = {
  planner: "bg-gold-soft text-ink",
  "codex-agent": "bg-ink text-paper",
  "llm-adapter": "bg-fern/15 text-fern border-fern/30",
  packager: "bg-rust/15 text-rust",
};

export function GenerationPanel({
  run,
  events,
  speed = 8,
}: {
  run: GenerationRun | null;
  events: GenerationEvent[];
  speed?: number;
}) {
  const [played, setPlayed] = useState(0);
  const [running, setRunning] = useState(false);
  const [currentSpeed, setCurrentSpeed] = useState(speed);

  useEffect(() => {
    if (!running) return;
    if (played >= events.length) {
      setRunning(false);
      return;
    }
    const next = events[played];
    const delay = Math.max(80, (next.delay_ms ?? 600) / currentSpeed);
    const timer = setTimeout(() => setPlayed((p) => p + 1), delay);
    return () => clearTimeout(timer);
  }, [played, running, events, currentSpeed]);

  const visible = events.slice(0, played);
  const isComplete = played >= events.length;

  const summary = run?.summary ?? {};
  const stats = useMemo(() => {
    return [
      { label: "Events", value: Number(summary.events_extracted ?? 0) },
      { label: "Officers", value: Number(summary.officers_named ?? 0) },
      { label: "OB numbers", value: Number(summary.ob_numbers_seen ?? 0) },
      { label: "Precedents", value: Number(summary.precedents_ranked ?? 0) },
    ];
  }, [summary]);

  if (!run) {
    return (
      <EmptyState
        title="No generation runs yet"
        body="Approve the plan, then click Generate. The Codex agent stream will appear here as a cinematic replay."
      />
    );
  }

  return (
    <div className="grid gap-4">
      <header className="surface flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="ink">run #{run.id}</Badge>
          <Badge variant="gold">{run.generator_mode}</Badge>
          <Badge variant="paper">{run.status}</Badge>
          <span className="mono text-xs text-ink/45">
            {run.duration_seconds ?? 0}s · {events.length} events
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => {
              if (isComplete) {
                setPlayed(0);
                setRunning(true);
              } else {
                setRunning((r) => !r);
              }
            }}
          >
            {isComplete ? "↻ Replay" : running ? "⏸ Pause" : "▶ Play"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setRunning(false);
              setPlayed(events.length);
            }}
          >
            Skip to end
          </Button>
          <div className="hidden sm:flex items-center gap-1 text-xs text-ink/55">
            <span>Speed</span>
            {[2, 4, 8, 16].map((s) => (
              <button
                key={s}
                onClick={() => setCurrentSpeed(s)}
                className={
                  "rounded px-2 py-1 transition " +
                  (s === currentSpeed
                    ? "bg-ink text-paper"
                    : "bg-paper-deep/60 hover:bg-ink/10")
                }
              >
                {s}×
              </button>
            ))}
          </div>
          <span className="ml-auto text-xs text-ink/45">
            {played}/{events.length}
          </span>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardBody className="!py-3">
              <div className="text-[10px] uppercase tracking-[0.14em] text-ink/45">{s.label}</div>
              <div className="serif text-2xl font-bold mt-0.5">
                {isComplete ? <NumberTicker value={s.value} /> : s.value}
              </div>
            </CardBody>
          </Card>
        ))}
      </section>

      <ol className="grid gap-2 max-h-[60vh] overflow-y-auto scrollbar-thin pr-1">
        {visible.map((ev) => (
          <li
            key={ev.id}
            className="surface relative overflow-hidden p-3 animate-slide-in"
          >
            <span className="absolute inset-y-0 left-0 w-0.5 bg-gold/0 group-hover:bg-gold transition-colors" />
            <div className="flex flex-wrap items-baseline gap-2">
              <span
                className={
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] " +
                  (ACTOR_TONE[ev.actor] ?? "bg-ink/5 text-ink")
                }
              >
                {ev.actor}
              </span>
              <span className="mono text-[11px] text-ink/35">{ev.kind}</span>
              <span className="ml-auto mono text-[11px] text-ink/35">+{ev.delay_ms}ms</span>
            </div>
            <div className="mt-1 text-sm font-medium">{ev.title}</div>
            {ev.detail ? (
              <p className="text-xs text-ink/60 mt-0.5">{ev.detail}</p>
            ) : null}
            {ev.file_path ? (
              <p className="mono text-[11px] text-fern mt-1.5 inline-flex items-center gap-1.5 rounded-md bg-fern/8 px-2 py-1">
                <span className="opacity-60">$</span>
                <span className="truncate">{ev.file_path}</span>
              </p>
            ) : null}
          </li>
        ))}
        {!isComplete && running ? (
          <li className="flex items-center gap-2 px-3 py-2 text-xs text-ink/45 animate-wakili-pulse">
            <span className="inline-block h-2 w-2 rounded-full bg-gold" />
            codex agent working…
          </li>
        ) : null}
        {isComplete ? (
          <li className="px-3 py-2 text-xs text-fern">
            ✓ Run complete · open Timeline · Petition · Precedents · or Export.
          </li>
        ) : null}
      </ol>
    </div>
  );
}
