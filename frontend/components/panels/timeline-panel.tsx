"use client";

import { useMemo, useState } from "react";
import type { EvidenceCodex } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Card, CardBody } from "../ui/card";
import { EmptyState } from "../ui/empty-state";

const KIND_TONE: Record<string, string> = {
  ob_extract: "bg-rust/10 text-rust border-rust/30",
  whatsapp_export: "bg-fern/10 text-fern border-fern/30",
  audio: "bg-gold-soft/70 text-ink border-gold/30",
  case_notes: "bg-ink/10 text-ink border-ink/20",
  medical_report: "bg-rust/10 text-rust border-rust/30",
  text: "bg-ink/5 text-ink border-ink/20",
};

export function TimelinePanel({ codex }: { codex: EvidenceCodex | null }) {
  const [openIds, setOpenIds] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<string>("all");

  const groupedByDate = useMemo(() => {
    if (!codex) return [];
    const filtered =
      filter === "all"
        ? codex.timeline
        : codex.timeline.filter((e) => e.source_kind === filter);
    const groups = new Map<string, typeof codex.timeline>();
    for (const e of filtered) {
      const key = e.date ?? "Undated";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(e);
    }
    return Array.from(groups.entries());
  }, [codex, filter]);

  if (!codex) {
    return <EmptyState title="No timeline yet" body="Approve the plan and run the generator to extract a chronology." />;
  }

  const kinds = Array.from(new Set(codex.timeline.map((e) => e.source_kind)));

  return (
    <div className="grid gap-4">
      <header className="grid grid-cols-2 gap-2 sm:grid-cols-5 sm:gap-3">
        <Stat label="Files indexed" value={codex.files_indexed} />
        <Stat label="Events extracted" value={codex.events_extracted} />
        <Stat label="Officers named" value={codex.officers_named} />
        <Stat label="OB numbers" value={codex.ob_numbers_seen} />
        <Stat label="Stations" value={codex.stations_named} />
      </header>

      {codex.gaps.length > 0 ? (
        <Card>
          <CardBody className="!py-3">
            <div className="text-[11px] uppercase tracking-[0.14em] text-rust">
              {codex.gaps.length} gap{codex.gaps.length > 1 ? "s" : ""} flagged in the chronology
            </div>
            <ul className="mt-2 grid gap-1 text-sm text-rust/85 list-disc pl-5">
              {codex.gaps.slice(0, 4).map((gap) => (
                <li key={`${gap.from}-${gap.to}`}>
                  <span className="mono">{gap.from} → {gap.to}</span> · {gap.days} days · {gap.note}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-3 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setFilter("all")}
              className={
                "rounded-full border px-3 py-1 text-xs " +
                (filter === "all"
                  ? "bg-ink text-paper border-ink"
                  : "border-ink/15 text-ink/70 hover:border-ink/30")
              }
            >
              All ({codex.events_extracted})
            </button>
            {kinds.map((k) => (
              <button
                key={k}
                onClick={() => setFilter(k)}
                className={
                  "rounded-full border px-3 py-1 text-xs " +
                  (filter === k
                    ? "bg-ink text-paper border-ink"
                    : "border-ink/15 text-ink/70 hover:border-ink/30")
                }
              >
                {k}
              </button>
            ))}
          </div>

          {groupedByDate.length === 0 ? (
            <EmptyState title="No events match" body="Try clearing the filter." />
          ) : (
            <div className="grid gap-4">
              {groupedByDate.map(([date, events]) => (
                <section key={date}>
                  <div className="sticky top-[64px] z-[5] mb-2 -ml-1 inline-flex items-center gap-2 rounded-full border border-ink/10 bg-paper/85 px-3 py-1 text-xs backdrop-blur-md">
                    <span className="mono">{date}</span>
                    <span className="text-ink/40">·</span>
                    <span className="text-ink/55">{events.length} event{events.length > 1 ? "s" : ""}</span>
                  </div>
                  <ol className="relative grid gap-2">
                    <span className="absolute left-3 top-1 bottom-1 w-px bg-ink/10" aria-hidden />
                    {events.map((event) => {
                      const open = openIds[event.id] ?? false;
                      return (
                        <li
                          key={event.id}
                          className="ml-1 grid grid-cols-[24px_1fr] gap-3 surface px-3 py-2.5"
                        >
                          <span className="mt-1 inline-block h-3 w-3 rounded-full bg-gold ring-4 ring-paper" />
                          <button
                            onClick={() => setOpenIds((s) => ({ ...s, [event.id]: !open }))}
                            className="text-left grid gap-1 focus-ring rounded"
                            aria-expanded={open}
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={
                                  "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] " +
                                  (KIND_TONE[event.source_kind] ?? KIND_TONE.text)
                                }
                              >
                                {event.source_kind}
                              </span>
                              <span className="text-[11px] text-ink/45">
                                {event.source_file}:{event.line_number}
                              </span>
                              <span className="ml-auto text-[10px] mono text-ink/30 hover:text-ink/60">
                                {event.id}
                              </span>
                            </div>
                            <p className="text-sm text-ink/85">{event.summary}</p>
                            {event.officers_in_context.length > 0 ? (
                              <div className="flex flex-wrap gap-1 pt-1">
                                {event.officers_in_context.map((officer, idx) => (
                                  <Badge key={`${officer.rank}-${idx}`} variant="paper">
                                    {officer.rank} {officer.name}
                                  </Badge>
                                ))}
                              </div>
                            ) : null}
                            {event.ob_numbers_in_context.length > 0 ? (
                              <div className="flex flex-wrap gap-1 pt-1">
                                {event.ob_numbers_in_context.map((ob) => (
                                  <Badge key={ob} variant="rust">OB {ob}</Badge>
                                ))}
                              </div>
                            ) : null}
                          </button>
                        </li>
                      );
                    })}
                  </ol>
                </section>
              ))}
            </div>
          )}
        </div>

        <aside className="grid gap-3 min-w-0 order-first lg:order-last lg:sticky lg:top-[80px] self-start">
          <Card>
            <CardBody>
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-2">Issue heatmap</h3>
              <ul className="grid gap-2">
                {codex.issue_heatmap.map((issue) => {
                  const max = Math.max(1, codex.issue_heatmap[0]?.score ?? 1);
                  return (
                    <li key={issue.name} className="grid gap-0.5">
                      <div className="flex items-baseline justify-between gap-2 text-sm">
                        <span>{issue.name}</span>
                        <span className="mono text-[11px] text-ink/45">{issue.score}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-paper-deep">
                        <div
                          className="h-full rounded-full bg-gold transition-[width] duration-700"
                          style={{ width: `${Math.min(100, (issue.score / max) * 100)}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-2">Officers</h3>
              <ul className="grid gap-1 text-sm">
                {codex.officers.map((o) => (
                  <li
                    key={`${o.rank}-${o.name}`}
                    className="flex items-baseline justify-between gap-2"
                  >
                    <span>{o.rank} {o.name}</span>
                    <span className="mono text-[11px] text-ink/45">{o.mentions}×</span>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink/45">{label}</div>
      <div className="mono text-xl font-semibold mt-0.5">{value}</div>
    </div>
  );
}
