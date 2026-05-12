"use client";

import { useState } from "react";
import type { ProceduralEngine } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Card, CardBody } from "../ui/card";
import { DownloadMenu } from "../ui/download-menu";
import { EmptyState } from "../ui/empty-state";
import { toast } from "@/lib/toast";
import { runDocumentDownload } from "./petition-panel";

const STATUS_TONE: Record<string, "fern" | "gold" | "rust"> = {
  pending: "fern",
  due_soon: "gold",
  overdue: "rust",
};

export function ProcedurePanel({
  data,
  caseId,
}: {
  data: ProceduralEngine | null;
  caseId?: number;
}) {
  if (!data) {
    return <EmptyState title="No procedural state yet" body="Generate the toolkit to surface deadlines and motions." />;
  }
  return (
    <div className="grid gap-4">
      <header className="surface px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="serif text-xl font-semibold tracking-tight">{data.track_label}</h2>
          {data.citation ? <Badge variant="paper">{data.citation}</Badge> : null}
        </div>
        <p className="mt-1 text-sm text-ink/55">
          Anchor: <span className="mono">{data.anchor_date}</span> · today:{" "}
          <span className="mono">{data.today}</span>
        </p>
      </header>

      <ol className="grid gap-2">
        {data.schedule.map((s, idx) => (
          <li
            key={`${s.filing}-${idx}`}
            className="grid grid-cols-[110px_1fr_auto] items-center gap-3 surface px-4 py-3"
          >
            <span className="mono text-sm">{s.deadline}</span>
            <div className="min-w-0">
              <div className="font-medium truncate">{s.filing}</div>
              <p className="text-xs text-ink/60 mt-0.5 line-clamp-2">{s.purpose}</p>
              {s.rule ? <p className="mono text-[11px] text-ink/40 mt-0.5">{s.rule}</p> : null}
            </div>
            <Badge variant={STATUS_TONE[s.status] ?? "paper"}>
              {s.status === "overdue"
                ? `${Math.abs(s.days_remaining)}d overdue`
                : `${s.days_remaining}d`}
            </Badge>
          </li>
        ))}
      </ol>

      {data.drafted_motions.length > 0 ? (
        <section>
          <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-2">
            Drafted motions ({data.drafted_motions.length}) — placeholders resolved at download
          </h3>
          <div className="grid gap-2">
            {data.drafted_motions.map((m, idx) => (
              <MotionCard
                key={`${m.filing}-${idx}`}
                motion={m}
                index={idx}
                caseId={caseId}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function MotionCard({
  motion,
  index,
  caseId,
}: {
  motion: ProceduralEngine["drafted_motions"][number];
  index: number;
  caseId?: number;
}) {
  const [busy, setBusy] = useState(false);
  const slug = (motion.filing || motion.template || `motion_${index}`)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_");
  return (
    <Card>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3">
          <span className="font-medium">{motion.filing}</span>
          <div className="flex items-center gap-3">
            {caseId != null ? (
              <DownloadMenu
                label="Motion"
                primaryKey="pdf"
                busy={busy}
                options={[
                  { key: "pdf", label: "PDF", description: "Self-contained · placeholders resolved" },
                  { key: "docx", label: "Word (.docx)", description: "Drive auto-converts to Google Docs" },
                  { key: "md", label: "Markdown", description: "Source for editing" },
                  { key: "drive", label: "Open in Google Drive", description: "Uploads & opens as a Doc copy" },
                ]}
                onSelect={async (k) => {
                  setBusy(true);
                  try {
                    await runDocumentDownload({
                      kind: "motion",
                      caseId,
                      fmt: k,
                      motionIndex: index,
                      filenameBase: `verda_case_${caseId}_${slug}`,
                    });
                  } catch (err) {
                    toast.error(
                      "Motion export failed",
                      err instanceof Error ? err.message : undefined,
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            ) : null}
            <span className="mono text-[11px] text-ink/45">
              {motion.template} <span className="ml-2 text-ink/30 group-open:hidden">↓</span>
              <span className="ml-2 text-ink/30 hidden group-open:inline">↑</span>
            </span>
          </div>
        </summary>
        <CardBody className="!pt-0">
          {/* `data-content="markdown"` opts this block into the global
              break-anywhere rules — long signature underscore runs and
              URL strings wrap mid-character instead of dragging the
              whole page sideways. */}
          <div data-content="markdown" className="min-w-0 max-w-full">
            <pre className="mono w-full rounded-lg border border-ink/8 bg-paper-deep/40 p-3 text-[11px] leading-relaxed">
              {motion.content}
            </pre>
          </div>
        </CardBody>
      </details>
    </Card>
  );
}
