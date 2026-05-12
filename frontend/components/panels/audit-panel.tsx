import type { AuditEntry } from "@/lib/types";
import { Badge } from "../ui/badge";
import { DateText } from "../ui/date-text";
import { EmptyState } from "../ui/empty-state";

const ACTOR_TONE: Record<string, "ink" | "gold" | "fern" | "rust" | "paper"> = {
  "kenyalaw-mcp": "fern",
  "africanlii-mcp": "fern",
  "case-knowledge-mcp": "fern",
  intake: "gold",
  packager: "gold",
  exporter: "gold",
  orchestrator: "ink",
  planner: "ink",
  lawyer: "rust",
  "llm-adapter": "paper",
};

export function AuditPanel({ entries }: { entries: AuditEntry[] }) {
  if (!entries.length) {
    return <EmptyState title="No audit entries yet" body="Every MCP call, every Codex prompt, and every export will appear here." />;
  }
  return (
    <ol className="grid gap-2">
      {entries.map((e) => (
        <li
          key={e.id}
          className="grid grid-cols-[160px_minmax(0,1fr)] items-start gap-3 surface px-3 py-2.5 text-sm"
        >
          <div className="flex flex-col items-start gap-1 self-start">
            <Badge variant={ACTOR_TONE[e.actor] ?? "paper"} className="self-start whitespace-nowrap">
              {e.actor}
            </Badge>
            <DateText iso={e.created_at} className="mono text-[11px]" />
          </div>
          <div className="grid gap-1 min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="font-medium">{e.action}</span>
              {e.case_id ? <span className="mono text-[11px] text-ink/40">case #{e.case_id}</span> : null}
            </div>
            {e.resource ? (
              <span className="mono text-[11px] text-ink/50 break-all">{e.resource}</span>
            ) : null}
            {Object.keys(e.payload ?? {}).length > 0 ? (
              <details className="text-[11px] text-ink/50">
                <summary className="cursor-pointer hover:text-ink/70">payload</summary>
                <pre className="mt-1 overflow-x-auto rounded bg-paper-deep/40 p-2 mono text-[11px] whitespace-pre-wrap break-all">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
