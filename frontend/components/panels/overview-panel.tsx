import Link from "next/link";
import type { CaseDetail } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Card, CardBody, CardHeader } from "../ui/card";
import { EmptyState } from "../ui/empty-state";

export function OverviewPanel({ data }: { data: CaseDetail }) {
  const c = data;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="grid gap-4">
        <Card>
          <CardHeader
            title="Evidence inventory"
            right={<Badge variant="paper">{c.files.length} files</Badge>}
          />
          <CardBody className="!pt-3">
            {c.files.length === 0 ? (
              <EmptyState
                title="No evidence yet"
                body="Drop files in the intake zone on the home page."
              />
            ) : (
              <ul className="grid gap-1.5">
                {c.files.map((f) => (
                  <li
                    key={f.id}
                    className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border border-ink/8 bg-paper-deep/30 px-3 py-2 text-sm"
                  >
                    <span className="truncate" title={f.original_name}>{f.original_name}</span>
                    <Badge variant="paper">{f.evidence_kind}</Badge>
                    <span className="mono text-[11px] text-ink/40">
                      {(f.size_bytes / 1024).toFixed(1)} kB
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Plan" subtitle={c.plan?.summary ?? "Plan will appear once evidence is ingested."} />
          <CardBody className="!pt-2">
            {c.plan ? (
              <ul className="grid gap-2 text-sm">
                {c.plan.modules.map((m) => (
                  <li key={m.key} className="grid grid-cols-[1fr_auto] items-baseline gap-3 rounded-md bg-paper-deep/30 px-3 py-2">
                    <div className="min-w-0">
                      <span className="font-medium">{m.name}</span>
                      <p className="mt-0.5 text-xs text-ink/55 line-clamp-2">{m.rationale}</p>
                    </div>
                    <span className="mono text-[11px] text-ink/40">~{m.estimated_minutes}m</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink/55">Upload evidence and the planner will run automatically.</p>
            )}
            <div className="mt-3">
              <Link href={`/cases/${c.id}?view=plan`} className="text-xs text-ink/65 underline decoration-gold underline-offset-2 hover:text-ink">
                Review plan →
              </Link>
            </div>
          </CardBody>
        </Card>

        {c.latest_run ? (
          <Card>
            <CardHeader title="Latest generation run" right={<Badge variant="paper">run #{c.latest_run.id}</Badge>} />
            <CardBody className="!pt-2">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
                <Stat label="Mode" value={c.latest_run.generator_mode} />
                <Stat label="Duration" value={`${c.latest_run.duration_seconds ?? 0}s`} />
                <Stat label="Status" value={c.latest_run.status} />
                <Stat label="Started" value={c.latest_run.started_at.slice(11, 16)} />
              </div>
              <Link
                href={`/cases/${c.id}?view=generation`}
                className="mt-3 inline-block text-xs text-ink/65 underline decoration-gold underline-offset-2 hover:text-ink"
              >
                Replay agent stream →
              </Link>
            </CardBody>
          </Card>
        ) : null}
      </div>

      <aside className="grid gap-4">
        <Card tone="deep">
          <CardBody>
            <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-2">Next steps</h3>
            <ol className="grid gap-2 text-sm list-decimal pl-5 text-ink/80">
              <li>Review the plan; approve when ready.</li>
              <li>Run generation; replay the Codex agent stream.</li>
              <li>Inspect the timeline and the precedent list.</li>
              <li>Edit the petition draft; sign and file.</li>
              <li>Export the bundle (zip / encrypted / Docker / USB).</li>
            </ol>
          </CardBody>
        </Card>
        <Card tone="ink">
          <CardBody>
            <h3 className="text-[11px] uppercase tracking-[0.16em] text-gold mb-2">Keyboard</h3>
            <ul className="grid gap-1.5 text-xs text-paper/80">
              {[
                ["1–9", "Switch panels"],
                ["⌘K", "Command palette"],
                ["g · c", "Go to all cases"],
              ].map(([k, d]) => (
                <li key={k} className="flex items-center justify-between gap-2">
                  <span className="kbd !bg-paper/10 !text-paper !border-paper/15">{k}</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-paper-deep/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink/45">{label}</div>
      <div className="mono font-semibold mt-0.5">{value}</div>
    </div>
  );
}
