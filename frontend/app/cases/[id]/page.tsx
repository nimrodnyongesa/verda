import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { CaseHeader } from "@/components/workspace/case-header";
import { WorkspaceSidebar } from "@/components/workspace/sidebar";
import { getActivePanel } from "@/lib/panels";
import { OverviewPanel } from "@/components/panels/overview-panel";
import { PlanPanel } from "@/components/panels/plan-panel";
import { TimelinePanel } from "@/components/panels/timeline-panel";
import { GenerationPanel } from "@/components/panels/generation-panel";
import { PetitionPanel } from "@/components/panels/petition-panel";
import { PrecedentsPanel } from "@/components/panels/precedents-panel";
import { ProcedurePanel } from "@/components/panels/procedure-panel";
import { AuditPanel } from "@/components/panels/audit-panel";
import { ExportPanelV2 } from "@/components/panels/export-panel";

export const dynamic = "force-dynamic";

type RawSearchParams = Promise<{ view?: string }>;

export default async function CaseWorkspace({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: RawSearchParams;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const caseId = Number(id);
  if (!Number.isFinite(caseId)) notFound();

  const detail = await api.getCase(caseId).catch(() => null);
  if (!detail) notFound();
  const c = detail.case;
  const view = getActivePanel(sp?.view ?? null);

  // Eagerly fetch the panel data on the server based on the view to keep
  // requests close to first paint.
  const [timeline, precedents, procedure, petition, runResult, auditResult] = await Promise.all([
    view === "timeline" ? api.timeline(caseId).catch(() => null) : null,
    view === "precedents" ? api.precedents(caseId).catch(() => null) : null,
    view === "procedure" ? api.procedure(caseId).catch(() => null) : null,
    view === "petition" ? api.petition(caseId).catch(() => null) : null,
    view === "generation" ? api.latestRun(caseId).catch(() => null) : null,
    view === "audit" ? api.audit(caseId).catch(() => ({ entries: [] })) : null,
  ]);

  return (
    <div className="app-shell py-4 grid gap-4 sm:py-6 sm:gap-5">
      <CaseHeader data={c} />
      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[200px_1fr]">
        <aside className="lg:sticky lg:top-[80px] self-start min-w-0">
          <WorkspaceSidebar />
        </aside>
        <section className="min-w-0">
          {view === "overview" && <OverviewPanel data={c} />}
          {view === "plan" && <PlanPanel plan={c.plan} caseId={caseId} />}
          {view === "generation" && (
            <GenerationPanel run={runResult?.run ?? null} events={runResult?.events ?? []} />
          )}
          {view === "timeline" && <TimelinePanel codex={timeline} />}
          {view === "petition" && <PetitionPanel markdown={petition} caseId={caseId} />}
          {view === "precedents" && <PrecedentsPanel data={precedents} />}
          {view === "procedure" && <ProcedurePanel data={procedure} caseId={caseId} />}
          {view === "audit" && <AuditPanel entries={auditResult?.entries ?? []} />}
          {view === "export" && (
            <ExportPanelV2 caseId={caseId} hasRun={!!c.latest_run} />
          )}
        </section>
      </div>
    </div>
  );
}
