"use client";

import type { ReactNode } from "react";
import type { CaseSummary } from "@/lib/types";
import Link from "next/link";
import { Badge } from "./ui/badge";
import { DateText } from "./ui/date-text";
import { EmptyState } from "./ui/empty-state";
import { useT } from "@/lib/i18n/provider";

const STATUS_TONE: Record<string, "gold" | "fern" | "rust" | "ink"> = {
  intake: "gold",
  generated: "fern",
  filed: "ink",
};

export function CaseList({
  cases,
  dense = false,
  renderTrailing,
  renderSubtitle,
}: {
  cases: CaseSummary[];
  dense?: boolean;
  renderTrailing?: (c: CaseSummary) => ReactNode;
  renderSubtitle?: (c: CaseSummary) => string;
}) {
  const t = useT();
  if (!cases.length) {
    return (
      <EmptyState
        title={t("caseList.emptyTitle")}
        body={t("caseList.emptyBody")}
      />
    );
  }
  return (
    <ul className="grid gap-2.5">
      {cases.map((c) => (
        <li key={c.id} className="relative">
          <Link
            href={`/cases/${c.id}`}
            className="group block surface p-4 transition hover:border-gold/45 hover:shadow-[0_12px_36px_-18px_rgba(212,165,52,.45)] focus-ring"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3
                className={
                  "font-semibold tracking-tight group-hover:text-ink " +
                  (dense ? "text-sm" : "text-base") +
                  // Reserve space on the right edge so the trailing menu has
                  // room to render without overlapping the title.
                  (renderTrailing ? " pr-28" : "")
                }
              >
                {c.title}
              </h3>
              <Badge variant={STATUS_TONE[c.status] ?? "paper"}>{c.status}</Badge>
            </div>
            {!dense && c.description ? (
              <p className="text-sm text-ink/60 mt-1 line-clamp-2 pretty">{c.description}</p>
            ) : null}
            {renderSubtitle ? (
              <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-ink/45">
                {renderSubtitle(c)}
              </p>
            ) : null}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] mono text-ink/45">
              <span>{t("caseList.metaCase", { id: c.id })}</span>
              <Dot />
              <span>{c.jurisdiction.toUpperCase()}</span>
              <Dot />
              <span>{c.legal_track}</span>
              <Dot />
              <span>{t("caseList.metaFiles", { count: c.file_count ?? 0 })}</span>
              <Dot />
              <span className="inline-flex items-center gap-1">
                {t("caseList.metaUpdated")} <DateText iso={c.updated_at ?? c.created_at} />
              </span>
            </div>
          </Link>
          {renderTrailing ? (
            <div className="absolute right-3 top-3 z-10">{renderTrailing(c)}</div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function Dot() {
  return <span aria-hidden className="text-ink/20">·</span>;
}
