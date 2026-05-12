"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { EmptyState } from "../ui/empty-state";
import { DownloadMenu } from "../ui/download-menu";
import { toast } from "@/lib/toast";

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(s: string): string {
  return escapeHtml(s)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="mono">$1</code>')
    .replace(
      /(https?:\/\/[^\s)\"]+)/g,
      '<a class="gold-underline pb-0.5 hover:text-ink" href="$1" target="_blank" rel="noreferrer">$1 ↗</a>'
    );
}

type Section = { id: string; level: number; text: string };

function renderMarkdown(md: string): { html: string; sections: Section[] } {
  const lines = md.split("\n");
  const out: string[] = [];
  const sections: Section[] = [];
  let inList: "ul" | "ol" | null = null;
  let para: string[] = [];

  function flushPara() {
    if (para.length) {
      out.push(`<p>${renderInline(para.join(" "))}</p>`);
      para = [];
    }
  }
  function closeList() {
    if (inList) {
      out.push(`</${inList}>`);
      inList = null;
    }
  }

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line) {
      flushPara();
      closeList();
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      flushPara();
      closeList();
      const level = h[1].length;
      const text = h[2];
      const id = "s-" + text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      out.push(`<h${level} id="${id}">${renderInline(text)}</h${level}>`);
      sections.push({ id, level, text });
      continue;
    }
    const ol = /^(\d+)\.\s+(.*)$/.exec(line);
    if (ol) {
      flushPara();
      if (inList !== "ol") {
        closeList();
        out.push("<ol>");
        inList = "ol";
      }
      out.push(`<li>${renderInline(ol[2])}</li>`);
      continue;
    }
    const ul = /^[-*]\s+(.*)$/.exec(line);
    if (ul) {
      flushPara();
      if (inList !== "ul") {
        closeList();
        out.push("<ul>");
        inList = "ul";
      }
      out.push(`<li>${renderInline(ul[1])}</li>`);
      continue;
    }
    if (inList) {
      flushPara();
      closeList();
    }
    para.push(line);
  }
  flushPara();
  closeList();
  return { html: out.join("\n"), sections };
}

export function PetitionPanel({
  markdown,
  caseId,
}: {
  markdown: string | null;
  caseId?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const { html, sections } = useMemo(
    () => (markdown ? renderMarkdown(markdown) : { html: "", sections: [] }),
    [markdown]
  );

  useEffect(() => {
    if (!sections.length || !ref.current) return;
    const ids = sections.map((s) => s.id);
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: [0, 1] }
    );
    for (const id of ids) {
      const node = document.getElementById(id);
      if (node) obs.observe(node);
    }
    return () => obs.disconnect();
  }, [sections]);

  if (!markdown) {
    return <EmptyState title="No petition draft yet" body="The petition will appear here after generation completes." />;
  }

  const copySection = async (id: string) => {
    const node = document.getElementById(id);
    if (!node) return;
    const range = document.createRange();
    let end: Element | null = node;
    while (end?.nextElementSibling) {
      const tag = end.nextElementSibling.tagName.toLowerCase();
      if (/^h[1-6]$/.test(tag)) break;
      end = end.nextElementSibling;
    }
    range.setStartBefore(node);
    range.setEndAfter(end ?? node);
    const text = range.toString();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* ignore */
    }
  };

  const topSections = sections.filter((s) => s.level <= 2);

  return (
    <div className="grid gap-4">
      {caseId ? (
        <PetitionExportRow caseId={caseId} />
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
      <article
        ref={ref}
        data-content="markdown"
        className="prose-petition serif surface p-7 max-w-none min-w-0 overflow-hidden break-words [overflow-wrap:anywhere]"
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <aside className="min-w-0 lg:block">
        <details className="surface p-4 lg:sticky lg:top-[80px] [&[open]_summary_.chev]:rotate-180" open>
          <summary className="flex cursor-pointer items-center justify-between gap-2 text-[11px] uppercase tracking-[0.16em] text-ink/45 lg:cursor-default">
            <span>Sections</span>
            <span aria-hidden className="chev transition-transform lg:hidden">▾</span>
          </summary>
          <ul className="mt-3 grid gap-1 text-sm">
            {topSections.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className={
                    "block truncate rounded px-2 py-1 transition " +
                    (activeId === s.id
                      ? "bg-ink text-paper"
                      : "text-ink/65 hover:bg-ink/5 hover:text-ink") +
                    (s.level === 2 ? " pl-4" : "")
                  }
                >
                  {s.text}
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {topSections.slice(0, 3).map((s) => (
              <button
                key={s.id}
                onClick={() => copySection(s.id)}
                className="min-h-[36px] rounded-md border border-ink/12 bg-paper-deep/40 px-2 py-1 text-[11px] text-ink/65 hover:bg-ink/5 focus-ring"
              >
                Copy {s.text.slice(0, 14)}…
              </button>
            ))}
          </div>
        </details>
      </aside>
      </div>
    </div>
  );
}

/**
 * Petition export row — single dropdown button (PDF default · DOCX · MD ·
 * Open in Drive). Uses ``runDocumentDownload`` so the placeholder pass on
 * the backend is the same regardless of which target is picked.
 */
function PetitionExportRow({ caseId }: { caseId: number }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-ink/10 bg-paper-deep/40 px-4 py-2.5 text-[11px] uppercase tracking-[0.16em] text-ink/55">
      <span>Petition draft · placeholders resolved on download</span>
      <DownloadMenu
        label="Petition"
        primaryKey="pdf"
        busy={busy}
        options={[
          { key: "pdf", label: "PDF", description: "Self-contained · placeholders resolved" },
          { key: "docx", label: "Word (.docx)", description: "Drive auto-converts to Google Docs" },
          { key: "md", label: "Markdown", description: "Source for editing in any editor" },
          { key: "drive", label: "Open in Google Drive", description: "Uploads & opens as a Doc copy" },
        ]}
        onSelect={async (k) => {
          setBusy(true);
          try {
            await runDocumentDownload({
              kind: "petition",
              caseId,
              fmt: k,
              filenameBase: `verda_case_${caseId}_petition`,
            });
          } catch (err) {
            toast.error("Petition export failed", err instanceof Error ? err.message : undefined);
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}

/**
 * Shared download path. Returns once the download has been triggered
 * (PDF/DOCX/MD) or once the Drive upload tab has been opened (drive).
 *
 * For "drive" we DOCX-export first, then open
 * https://drive.google.com/u/0/?usp=docs (the user-controlled upload page)
 * with a transferred blob URL — Google Drive's upload widget then
 * auto-creates a Google Doc copy on import. The user's Drive account is
 * the trust boundary; we never POST anything ourselves.
 */
export async function runDocumentDownload(opts: {
  kind: "petition" | "motion";
  caseId: number;
  fmt: string;
  motionIndex?: number;
  filenameBase: string;
}): Promise<void> {
  const { kind, caseId, fmt, motionIndex, filenameBase } = opts;
  const apiPath =
    kind === "petition"
      ? `/api/be/cases/${caseId}/petition/document`
      : `/api/be/cases/${caseId}/motions/${motionIndex ?? 0}`;
  const targetFmt = fmt === "drive" ? "docx" : fmt;
  const ext = targetFmt === "docx" ? "docx" : targetFmt === "md" ? "md" : "pdf";
  const res = await fetch(`${apiPath}?fmt=${encodeURIComponent(targetFmt)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  if (fmt === "drive") {
    // Best-effort: the actual Drive upload requires Google's OAuth flow which
    // we deliberately don't proxy. We download the .docx and open Drive's
    // "new" upload page in a new tab; the lawyer drops the file there and
    // Drive auto-creates the Google Doc copy.
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filenameBase}.${ext}`;
    a.click();
    window.open("https://drive.google.com/drive/u/0/", "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    toast.success(
      "Drive upload",
      "DOCX downloaded · drop it on Google Drive — it auto-converts to a Google Doc."
    );
    return;
  }

  const a = document.createElement("a");
  a.href = url;
  a.download = `${filenameBase}.${ext}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  toast.success("Download ready", `${filenameBase}.${ext}`);
}
