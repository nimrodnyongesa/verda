"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Plan } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardBody, CardHeader } from "../ui/card";
import { EmptyState } from "../ui/empty-state";
import { toast } from "@/lib/toast";
import { confirm as customConfirm } from "@/lib/dialog";
import { usePermissions } from "@/components/auth/permissions-provider";
import { Permissions } from "@/lib/auth/permissions";

async function postBe<T>(path: string): Promise<T> {
  const res = await fetch(`/api/be${path}`, { method: "POST" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export function PlanPanel({ plan, caseId }: { plan: Plan | null; caseId: number }) {
  const router = useRouter();
  const { has } = usePermissions();
  const canApprove = has(Permissions.PlanApprove);
  const canGenerate = has(Permissions.GenerationRun);
  const canWrite = has(Permissions.CasesWrite);
  const [busy, setBusy] = useState<"none" | "approve" | "rebuild" | "generate">("none");
  const [skipped, setSkipped] = useState<Record<string, boolean>>({});
  const [confidence, setConfidence] = useState<Record<string, number>>({});
  const [approved, setApproved] = useState(plan?.approved ?? false);

  if (!plan) {
    return (
      <EmptyState
        title="No plan yet"
        body="Upload evidence and the planner will run automatically. The plan must be approved before generation."
      />
    );
  }

  const approve = async () => {
    setBusy("approve");
    try {
      await postBe(`/cases/${caseId}/plan/approve`);
      setApproved(true);
      toast.success("Plan approved");
    } catch (e) {
      toast.error("Approve failed", e instanceof Error ? e.message : undefined);
    } finally {
      setBusy("none");
    }
  };

  const rebuild = async () => {
    if (approved) {
      const ok = await customConfirm({
        title: "Rebuild plan?",
        body:
          "Rebuilding overwrites the saved plan and resets your approval. You'll need to review and approve the new plan before generation can run.",
        confirmLabel: "Rebuild plan",
        cancelLabel: "Keep current",
        variant: "warning",
      });
      if (!ok) return;
    }
    setBusy("rebuild");
    try {
      await postBe(`/cases/${caseId}/plan`);
      setApproved(false);
      toast.success("Plan rebuilt");
      router.refresh();
    } catch (e) {
      toast.error("Rebuild failed", e instanceof Error ? e.message : undefined);
    } finally {
      setBusy("none");
    }
  };

  const generate = async () => {
    setBusy("generate");
    try {
      if (!approved) {
        await postBe(`/cases/${caseId}/plan/approve`);
        setApproved(true);
      }
      const result = await postBe<{ run_id: number }>(`/cases/${caseId}/generate`);
      toast.success("Toolkit generated", `Run #${result.run_id}`);
      router.push(`/cases/${caseId}?view=generation`);
      router.refresh();
    } catch (e) {
      toast.error("Generate failed", e instanceof Error ? e.message : undefined);
    } finally {
      setBusy("none");
    }
  };

  return (
    <div className="grid gap-4">
      <header className="surface px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-2">
          <Badge variant="ink">Track · {plan.legal_track_label}</Badge>
          {plan.citation ? <Badge variant="paper">{plan.citation}</Badge> : null}
          {approved ? <Badge variant="fern">Approved by lawyer</Badge> : <Badge variant="rust">Pending approval</Badge>}
        </div>
        <p className="mt-2 text-sm text-ink/70">{plan.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            onClick={approve}
            disabled={approved || busy !== "none" || !canApprove}
            title={
              !canApprove
                ? "Your role can't approve a plan — a lawyer must sign off."
                : undefined
            }
          >
            {approved ? "Approved" : busy === "approve" ? "Approving…" : "Approve plan"}
          </Button>
          <Button
            variant="secondary"
            onClick={generate}
            disabled={busy !== "none" || !canGenerate || (!approved && !canApprove)}
            title={
              !canGenerate
                ? "Your role can't run generation."
                : !approved && !canApprove
                ? "Plan must be approved by a lawyer before generation."
                : undefined
            }
          >
            {busy === "generate" ? "Generating…" : "Generate toolkit"}
          </Button>
          <Button
            variant="outline"
            onClick={rebuild}
            disabled={busy !== "none" || !canWrite}
            title={!canWrite ? "Read-only access — can't rebuild the plan." : undefined}
          >
            {busy === "rebuild" ? "Rebuilding…" : "Rebuild plan"}
          </Button>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2">
        {plan.modules.map((m) => {
          const skip = skipped[m.key] ?? false;
          const conf = confidence[m.key] ?? 0.85;
          return (
            <Card key={m.key} className={skip ? "opacity-60" : ""}>
              <CardHeader
                title={m.name}
                right={<Badge variant="gold">~{m.estimated_minutes}m</Badge>}
              />
              <CardBody className="!pt-3 grid gap-3">
                <p className="text-sm text-ink/70">{m.rationale}</p>
                <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-ink/55">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={!skip}
                      onChange={(e) => setSkipped((s) => ({ ...s, [m.key]: !e.target.checked }))}
                      className="h-3.5 w-3.5 accent-gold"
                    />
                    Include
                  </label>
                  <span className="mono">skill · {m.key}</span>
                </div>
                <label className="grid gap-1 text-[11px] text-ink/55">
                  <span className="flex items-center justify-between">
                    <span>Confidence threshold</span>
                    <span className="mono">{conf.toFixed(2)}</span>
                  </span>
                  <input
                    type="range"
                    min={0.5}
                    max={0.99}
                    step={0.01}
                    value={conf}
                    onChange={(e) =>
                      setConfidence((s) => ({ ...s, [m.key]: parseFloat(e.target.value) }))
                    }
                    className="accent-gold"
                  />
                </label>
              </CardBody>
            </Card>
          );
        })}
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <Card tone="deep">
          <CardBody>
            <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink/45 mb-2">Suggested deadlines</h3>
            {plan.deadlines.length === 0 ? (
              <p className="text-xs text-ink/55">No anchored dates yet.</p>
            ) : (
              <ul className="grid gap-2 text-sm">
                {plan.deadlines.map((d) => (
                  <li key={d.label} className="flex items-baseline justify-between gap-3">
                    <span className="truncate">{d.label}</span>
                    <span className="mono text-xs">{d.date}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <h3 className="text-[11px] uppercase tracking-[0.16em] text-rust mb-2">Risks flagged</h3>
            {plan.risks.length === 0 ? (
              <p className="text-xs text-ink/55">No risks flagged.</p>
            ) : (
              <ul className="grid gap-1.5 text-sm text-rust/85 list-disc pl-5">
                {plan.risks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
