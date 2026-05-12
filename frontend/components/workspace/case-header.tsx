"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CaseDetail } from "@/lib/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { toast } from "@/lib/toast";
import { confirm as customConfirm } from "@/lib/dialog";
import { useT } from "@/lib/i18n/provider";

async function postBe<T>(path: string): Promise<T> {
  const res = await fetch(`/api/be${path}`, { method: "POST" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

async function patchBe<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/be${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

// Auto-titles created by the upload zone are shaped:
//   "Untitled case · 5/5/2026"
// We split on " · " so the editable text is just the prefix; the timestamp
// suffix (everything from the first " · " onward) survives unchanged.
function splitTitle(full: string): { prefix: string; suffix: string } {
  const idx = full.indexOf(" · ");
  if (idx === -1) return { prefix: full, suffix: "" };
  return { prefix: full.slice(0, idx), suffix: full.slice(idx) };
}

export function CaseHeader({ data }: { data: CaseDetail }) {
  const t = useT();
  const router = useRouter();
  const [busy, setBusy] = useState<"none" | "approve" | "generate">("none");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const deadline = useMemo(() => {
    const ds = data.plan?.deadlines?.[0];
    if (!ds) return null;
    const t = Date.parse(ds.date);
    if (Number.isNaN(t)) return null;
    const days = Math.round((t - now) / (1000 * 60 * 60 * 24));
    return { label: ds.label, date: ds.date, days };
  }, [data.plan, now]);

  const approved = !!data.plan?.approved;
  const hasPlan = !!data.plan;
  const hasRun = !!data.latest_run;

  const onApprove = async () => {
    setBusy("approve");
    try {
      await postBe(`/cases/${data.id}/plan/approve`);
      toast.success(
        t("workspace.caseHeader.approvedTitle"),
        t("workspace.caseHeader.approvedBody"),
      );
      router.refresh();
    } catch (e) {
      toast.error(t("workspace.caseHeader.approveFailed"), e instanceof Error ? e.message : undefined);
    } finally {
      setBusy("none");
    }
  };

  const onGenerate = async () => {
    if (hasRun) {
      const ok = await customConfirm({
        title: t("workspace.caseHeader.rerunTitle"),
        body: t("workspace.caseHeader.rerunBody"),
        confirmLabel: t("workspace.caseHeader.rerunConfirm"),
        cancelLabel: t("workspace.caseHeader.rerunCancel"),
        variant: "warning",
      });
      if (!ok) return;
    }
    setBusy("generate");
    try {
      if (!approved) await postBe(`/cases/${data.id}/plan/approve`);
      const result = await postBe<{ run_id: number; duration_seconds: number; summary: { events_extracted?: number } }>(
        `/cases/${data.id}/generate`
      );
      toast.success(
        t("workspace.caseHeader.generatedTitle"),
        t("workspace.caseHeader.generatedBody", {
          run: result.run_id,
          seconds: result.duration_seconds,
          events: result.summary.events_extracted ?? "?",
        }),
      );
      router.push(`/cases/${data.id}?view=generation`);
      router.refresh();
    } catch (e) {
      toast.error(t("workspace.caseHeader.generationFailed"), e instanceof Error ? e.message : undefined);
    } finally {
      setBusy("none");
    }
  };

  return (
    <header className="surface px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-baseline gap-2 text-xs text-ink/45">
        <Link href="/cases" className="underline-offset-2 hover:text-ink hover:underline">
          {t("workspace.caseHeader.casesCrumb")}
        </Link>
        <span>/</span>
        <span className="mono">{t("workspace.caseHeader.caseNumber", { id: data.id })}</span>
      </div>
      <EditableTitle caseId={data.id} fullTitle={data.title} />

      <p className="mt-2 max-w-3xl text-sm text-ink/65 pretty break-words">{data.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="ink">{data.status}</Badge>
        <Badge variant="gold">{data.jurisdiction.toUpperCase()}</Badge>
        <Badge variant="paper">{data.legal_track}</Badge>
        {deadline ? <DeadlinePill deadline={deadline} /> : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 [&>*]:min-h-[40px]">
        {hasPlan && !approved ? (
          <Button onClick={onApprove} variant="primary" size="sm" disabled={busy !== "none"}>
            {busy === "approve"
              ? t("workspace.caseHeader.approving")
              : t("workspace.caseHeader.approvePlan")}
          </Button>
        ) : null}
        {hasPlan ? (
          <Button onClick={onGenerate} variant="secondary" size="sm" disabled={busy !== "none"}>
            {busy === "generate"
              ? t("workspace.caseHeader.generating")
              : hasRun
              ? t("workspace.caseHeader.regenerate")
              : t("workspace.caseHeader.generate")}
          </Button>
        ) : null}
        <Link
          href={`/cases/${data.id}?view=export`}
          className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-lg border border-ink/12 bg-white px-3 py-2 text-xs text-ink/70 hover:border-ink/25 hover:text-ink focus-ring"
        >
          {t("workspace.caseHeader.export")}
        </Link>
      </div>
    </header>
  );
}

function DeadlinePill({ deadline }: { deadline: { label: string; date: string; days: number } }) {
  const t = useT();
  const tone =
    deadline.days < 0 ? "rust" : deadline.days <= 3 ? "rust" : deadline.days <= 7 ? "gold" : "fern";
  const text =
    deadline.days < 0
      ? t("workspace.caseHeader.deadlineOverdue", { days: Math.abs(deadline.days) })
      : t("workspace.caseHeader.deadlineDue", {
          days: deadline.days,
          label: deadline.label.toLowerCase(),
        });
  return (
    <Badge variant={tone}>
      <span className="mono">{deadline.date}</span>
      <span className="mx-1 opacity-50">·</span>
      <span>{text}</span>
    </Badge>
  );
}

function EditableTitle({ caseId, fullTitle }: { caseId: number; fullTitle: string }) {
  const t = useT();
  const router = useRouter();
  const initial = useMemo(() => splitTitle(fullTitle), [fullTitle]);
  const [prefix, setPrefix] = useState(initial.prefix);
  const [suffix, setSuffix] = useState(initial.suffix);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(initial.prefix);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Keep local state in sync with server-supplied data when the route reloads.
  useEffect(() => {
    const next = splitTitle(fullTitle);
    setPrefix(next.prefix);
    setSuffix(next.suffix);
    setDraft(next.prefix);
  }, [fullTitle]);

  useEffect(() => {
    if (editing) {
      // Defer to next tick so the input is mounted.
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    }
  }, [editing]);

  const HEADING =
    "serif mt-2 text-xl sm:text-2xl md:text-3xl font-semibold leading-tight tracking-tight balanced break-words";

  async function commit() {
    const next = draft.trim();
    if (!next) {
      toast.error(t("workspace.caseHeader.titleEmptyError"));
      setDraft(prefix);
      setEditing(false);
      return;
    }
    if (next === prefix) {
      setEditing(false);
      return;
    }
    const newTitle = next + suffix;
    setSaving(true);
    // Optimistic update so the user sees the change immediately.
    setPrefix(next);
    setEditing(false);
    try {
      await patchBe(`/cases/${caseId}`, { title: newTitle });
      toast.success(t("workspace.caseHeader.titleSaved"));
      router.refresh();
    } catch (e) {
      // Roll back on failure.
      setPrefix(initial.prefix);
      setDraft(initial.prefix);
      toast.error(t("workspace.caseHeader.renameFailed"), e instanceof Error ? e.message : undefined);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setDraft(prefix);
    setEditing(false);
  }

  if (editing) {
    return (
      <h1 className={HEADING}>
        <span className="inline-flex flex-wrap items-baseline gap-x-1 gap-y-2">
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commit();
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
            }}
            onBlur={commit}
            disabled={saving}
            aria-label={t("workspace.caseHeader.titleAriaLabel")}
            maxLength={180}
            spellCheck
            className="serif min-w-0 max-w-full flex-1 rounded-md border border-gold/60 bg-paper-deep/50 px-2 py-1 text-xl font-semibold tracking-tight text-ink shadow-[0_0_0_4px_rgba(212,165,52,0.18)] outline-none focus:border-gold sm:text-2xl md:text-3xl"
            style={{ width: `${Math.max(8, draft.length + 1)}ch` }}
          />
          {suffix ? (
            <span className="font-semibold text-ink/45">{suffix}</span>
          ) : null}
        </span>
      </h1>
    );
  }

  return (
    <h1 className={HEADING}>
      <button
        type="button"
        onClick={() => setEditing(true)}
        title={t("workspace.caseHeader.titleEditTooltip")}
        aria-label={t("workspace.caseHeader.titleEditAria", { prefix })}
        className="group inline-flex flex-wrap items-baseline gap-x-1 gap-y-1 rounded-md text-left transition hover:bg-gold-soft/40 focus-ring"
      >
        <span className="rounded px-1 -mx-1 underline decoration-dotted decoration-gold/0 underline-offset-4 group-hover:decoration-gold/70 group-focus-visible:decoration-gold/70">
          {prefix}
        </span>
        {suffix ? <span className="text-ink/45">{suffix}</span> : null}
        <span
          aria-hidden
          className="ml-1 inline-flex h-6 w-6 shrink-0 self-center items-center justify-center rounded-full bg-paper-deep/0 text-[12px] text-ink/30 transition group-hover:bg-paper-deep group-hover:text-ink/70 group-focus-visible:bg-paper-deep group-focus-visible:text-ink/70"
        >
          ✎
        </span>
      </button>
    </h1>
  );
}
