"use client";

import { useMemo, useState } from "react";
import type { PrecedentLinker } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Card, CardBody } from "../ui/card";
import { EmptyState } from "../ui/empty-state";

function RelevanceRing({ value }: { value: number }) {
  const v = Math.max(0, Math.min(1, value));
  const r = 14;
  const c = 2 * Math.PI * r;
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden>
      <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(10,20,41,.08)" strokeWidth="3" />
      <circle
        cx="18"
        cy="18"
        r={r}
        fill="none"
        stroke="var(--color-gold)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={`${c * v} ${c}`}
        transform="rotate(-90 18 18)"
      />
      <text x="18" y="20" textAnchor="middle" className="mono" fontSize="9" fill="var(--color-ink)">
        {Math.round(v * 100)}
      </text>
    </svg>
  );
}

export function PrecedentsPanel({ data }: { data: PrecedentLinker | null }) {
  const [courtFilter, setCourtFilter] = useState<string>("all");

  const courts = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.results.map((r) => r.court)));
  }, [data]);

  const results = useMemo(() => {
    if (!data) return [];
    return courtFilter === "all" ? data.results : data.results.filter((r) => r.court === courtFilter);
  }, [data, courtFilter]);

  if (!data) {
    return <EmptyState title="No precedents yet" body="Run generation to rank Kenya Law judgments against this case." />;
  }

  return (
    <div className="grid gap-4">
      <Card tone="deep">
        <CardBody className="!py-3 text-sm text-ink/70">
          {data.verification_note}
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center gap-1.5">
        <button
          onClick={() => setCourtFilter("all")}
          className={
            "rounded-full border px-3 py-1 text-xs " +
            (courtFilter === "all"
              ? "bg-ink text-paper border-ink"
              : "border-ink/15 text-ink/70 hover:border-ink/30")
          }
        >
          All courts ({data.results.length})
        </button>
        {courts.map((court) => (
          <button
            key={court}
            onClick={() => setCourtFilter(court)}
            className={
              "rounded-full border px-3 py-1 text-xs " +
              (courtFilter === court
                ? "bg-ink text-paper border-ink"
                : "border-ink/15 text-ink/70 hover:border-ink/30")
            }
          >
            {court}
          </button>
        ))}
      </div>

      <ul className="grid gap-3">
        {results.map((r) => (
          <li key={r.citation} className="group surface p-4 transition hover:border-gold/40">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <h3 className="serif text-lg font-semibold tracking-tight">{r.title}</h3>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <Badge variant="ink">{r.court}</Badge>
                  <Badge variant="paper">{r.year}</Badge>
                  {r.binding ? <Badge variant="fern">Binding</Badge> : null}
                  {r.articles_cited.map((a) => (
                    <Badge key={a} variant="gold">Art. {a}</Badge>
                  ))}
                </div>
              </div>
              <RelevanceRing value={r.relevance_score} />
            </div>
            <p className="mt-3 text-sm text-ink/75 leading-relaxed pretty">{r.summary}</p>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="mono text-ink/50">{r.citation}</span>
              <a
                className="gold-underline pb-0.5 hover:text-ink"
                href={r.url}
                target="_blank"
                rel="noreferrer"
              >
                Verify on Kenya Law ↗
              </a>
            </div>
            {r.match_reasons.length > 0 ? (
              <details className="mt-2 group/details">
                <summary className="cursor-pointer text-[11px] text-ink/45 hover:text-ink/70 list-none">
                  <span className="group-open/details:hidden">Why it matches ↓</span>
                  <span className="hidden group-open/details:inline">Hide ↑</span>
                </summary>
                <ul className="mt-1 grid gap-1 text-[11px] text-ink/55 pl-2 border-l-2 border-gold/40">
                  {r.match_reasons.map((reason, idx) => (
                    <li key={idx} className="pl-2">{reason}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
