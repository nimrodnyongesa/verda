"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CaseFolder, CaseSummary } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { ActionsMenu, type ActionItem } from "./ui/actions-menu";
import { DateText } from "./ui/date-text";
import { InfoTip } from "./ui/info-tip";
import { toast } from "@/lib/toast";
import { confirm as customConfirm, prompt as customPrompt } from "@/lib/dialog";
import { useSheetExit } from "@/lib/use-sheet-exit";
import { useT, useIntl } from "@/lib/i18n/provider";

const PER_PAGE = 25;
const FOLDER_ROW_CAP = 3; // cap visible folder rows; overflow → "View all"

type FolderListResponse = { folders: CaseFolder[] };
type CasesListResponse = {
  cases: CaseSummary[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
};

// ---------------------------------------------------------------------------
// Folder helpers
// ---------------------------------------------------------------------------

function pathToRoot(folders: CaseFolder[], leafId: number): CaseFolder[] {
  const byId = new Map(folders.map((f) => [f.id, f] as const));
  const out: CaseFolder[] = [];
  let cur: number | null | undefined = leafId;
  const seen = new Set<number>();
  while (cur != null) {
    if (seen.has(cur)) break;
    seen.add(cur);
    const node = byId.get(cur);
    if (!node) break;
    out.push(node);
    cur = node.parent_id;
  }
  return out.reverse();
}

function descendantIds(folders: CaseFolder[], rootId: number): Set<number> {
  const childrenOf = new Map<number, number[]>();
  for (const f of folders) {
    if (f.parent_id != null) {
      const arr = childrenOf.get(f.parent_id) ?? [];
      arr.push(f.id);
      childrenOf.set(f.parent_id, arr);
    }
  }
  const out = new Set<number>([rootId]);
  const queue = [rootId];
  while (queue.length) {
    const next = queue.shift()!;
    for (const id of childrenOf.get(next) ?? []) {
      if (!out.has(id)) {
        out.add(id);
        queue.push(id);
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Folder icon
// ---------------------------------------------------------------------------

function FolderIcon({
  open = false,
  className = "h-4 w-4",
}: {
  open?: boolean;
  className?: string;
}) {
  return open ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H3z" />
      <path d="M3 9h18l-2 9a2 2 0 0 1-2 1.6H5a2 2 0 0 1-2-1.6z" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

const iconBaseProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  className: "h-4 w-4",
  "aria-hidden": true,
} as const;

/**
 * Detailed outline folder for the folder-thumbnail tiles. Uses
 * currentColor so the bluish ink palette token (text-ink) drives the
 * stroke. The "filled" variant shows two file pages peeking up from
 * inside the folder so the lawyer can tell at a glance whether a
 * folder has contents without opening it.
 */
function FolderTileIcon({
  filled,
  className = "h-20 w-20",
}: {
  filled: boolean;
  className?: string;
}) {
  if (filled) {
    return (
      <svg
        viewBox="0 0 64 64"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        aria-hidden="true"
      >
        {/* Folder back panel — sticks up behind the front to give depth. */}
        <path d="M5 17 v-2 a3 3 0 0 1 3 -3 h13 l4 4 h31 a3 3 0 0 1 3 3 v9" />
        {/* Files peeking up from inside the folder. */}
        <rect x="14" y="18" width="22" height="14" rx="1.4" />
        <line x1="18" y1="23" x2="32" y2="23" strokeWidth="1.6" />
        <line x1="18" y1="27" x2="29" y2="27" strokeWidth="1.6" />
        <rect x="26" y="14" width="22" height="14" rx="1.4" />
        <line x1="30" y1="19" x2="44" y2="19" strokeWidth="1.6" />
        <line x1="30" y1="23" x2="40" y2="23" strokeWidth="1.6" />
        {/* Folder body — front panel comes after the files so it overlaps. */}
        <path d="M3 26 a3 3 0 0 1 3 -3 h52 a3 3 0 0 1 3 3 v24 a3 3 0 0 1 -3 3 h-52 a3 3 0 0 1 -3 -3 z" />
      </svg>
    );
  }
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M5 17 v-2 a3 3 0 0 1 3 -3 h13 l4 4 h31 a3 3 0 0 1 3 3 v9" />
      <path d="M3 26 a3 3 0 0 1 3 -3 h52 a3 3 0 0 1 3 3 v24 a3 3 0 0 1 -3 3 h-52 a3 3 0 0 1 -3 -3 z" />
      {/* Subtle horizontal line to suggest a flap fold. */}
      <line x1="3" y1="32" x2="61" y2="32" strokeOpacity="0.18" strokeWidth="1.6" />
    </svg>
  );
}

function OpenIcon() {
  return (
    <svg {...iconBaseProps}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}
function PlusIcon() {
  return (
    <svg {...iconBaseProps}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function PencilIcon() {
  return (
    <svg {...iconBaseProps}>
      <path d="M4 20h4l11-11-4-4L4 16z" />
      <path d="m13 5 4 4" />
    </svg>
  );
}
function FolderMoveIcon() {
  return (
    <svg {...iconBaseProps}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <path d="m11 13 3 0" />
      <path d="m13 11 2 2-2 2" />
    </svg>
  );
}
function DownloadIcon() {
  return (
    <svg {...iconBaseProps}>
      <path d="M12 4v12" />
      <path d="m6 12 6 6 6-6" />
      <path d="M5 21h14" />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg {...iconBaseProps}>
      <path d="M4 7h16" />
      <path d="M9 7V4h6v3" />
      <path d="M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

type FolderId = number | null; // null = root

type ListView = {
  cases: CaseSummary[];
  total: number;
  totalPages: number;
};

export function CasesPageClient({
  initialCases,
  initialFolders,
}: {
  initialCases: CaseSummary[];
  initialFolders: CaseFolder[];
}) {
  const router = useRouter();
  const t = useT();
  const { locale } = useIntl();
  // Reused locale-aware plural picker for "1 sub-folder" / "N sub-folders".
  const pluralRules = useMemo(() => new Intl.PluralRules(locale), [locale]);
  const [folders, setFolders] = useState<CaseFolder[]>(initialFolders);
  const [currentFolder, setCurrentFolder] = useState<FolderId>(null);
  const [page, setPage] = useState(1);
  const [list, setList] = useState<ListView>({
    cases: initialCases,
    total: initialCases.length,
    totalPages: Math.max(1, Math.ceil(initialCases.length / PER_PAGE)),
  });
  const [loading, setLoading] = useState(false);
  const [showAllFolders, setShowAllFolders] = useState(false);
  const [dragCaseId, setDragCaseId] = useState<number | null>(null);
  const [dropTargetFolderId, setDropTargetFolderId] = useState<FolderId | null>(null);

  const folderById = useMemo(
    () => new Map(folders.map((f) => [f.id, f] as const)),
    [folders]
  );

  // -------------------------------------------------------------------------
  // Server fetches
  // -------------------------------------------------------------------------

  const fetchFolders = useCallback(async () => {
    try {
      const r = await fetch("/api/be/folders");
      if (!r.ok) return;
      const data = (await r.json()) as FolderListResponse;
      setFolders(data.folders ?? []);
    } catch {
      /* keep last good list */
    }
  }, []);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      qs.set("page", String(page));
      qs.set("per_page", String(PER_PAGE));
      if (currentFolder == null) qs.set("root", "true");
      else qs.set("folder_id", String(currentFolder));
      const r = await fetch(`/api/be/cases?${qs.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as CasesListResponse;
      setList({
        cases: data.cases ?? [],
        total: data.total ?? 0,
        totalPages: data.total_pages ?? 1,
      });
    } catch (err) {
      toast.error(t("cases.toasts.loadFailed"), err instanceof Error ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [page, currentFolder, t]);

  // Reset page when the folder changes so the user is never stranded.
  useEffect(() => {
    setPage(1);
  }, [currentFolder]);

  useEffect(() => {
    void fetchCases();
  }, [fetchCases]);

  // -------------------------------------------------------------------------
  // Folders shown in this view
  // -------------------------------------------------------------------------

  const visibleFolders = useMemo(() => {
    return folders
      .filter((f) =>
        currentFolder == null ? f.parent_id == null : f.parent_id === currentFolder
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [folders, currentFolder]);

  // 4 × 3 = 12 visible at the largest breakpoint when capped.
  const folderRowItemsByBreakpoint = 4;
  const visibleCap = FOLDER_ROW_CAP * folderRowItemsByBreakpoint;
  const cappedFolders = showAllFolders
    ? visibleFolders
    : visibleFolders.slice(0, visibleCap);
  const hasOverflow = visibleFolders.length > cappedFolders.length;

  // -------------------------------------------------------------------------
  // Mutations
  // -------------------------------------------------------------------------

  const createFolder = useCallback(
    async (parent_id: FolderId) => {
      const parentName =
        parent_id == null ? "" : folderById.get(parent_id)?.name ?? "";
      const name = await customPrompt({
        title:
          parent_id == null
            ? t("cases.dialogs.createFolder.title")
            : t("cases.dialogs.createFolder.titleNested", { parent: parentName }),
        body: t("cases.dialogs.createFolder.body"),
        label: t("cases.dialogs.createFolder.label"),
        placeholder: t("cases.dialogs.createFolder.placeholder"),
        confirmLabel: t("cases.dialogs.createFolder.confirm"),
        cancelLabel: t("cases.dialogs.cancel"),
        validate: (v) =>
          v.trim().length === 0 ? t("cases.dialogs.createFolder.emptyError") : null,
      });
      if (!name) return;
      try {
        const r = await fetch("/api/be/folders", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ name: name.trim(), parent_id }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
        }
        const data = (await r.json()) as { folder: CaseFolder };
        setFolders((prev) => [...prev, data.folder]);
        toast.success(t("cases.toasts.folderCreated"), data.folder.name);
      } catch (err) {
        toast.error(t("cases.toasts.folderCreateFailed"), err instanceof Error ? err.message : undefined);
      }
    },
    [folderById, t]
  );

  const renameFolder = useCallback(async (folder: CaseFolder) => {
    const name = await customPrompt({
      title: t("cases.dialogs.renameFolder.title", { name: folder.name }),
      body: t("cases.dialogs.renameFolder.body"),
      label: t("cases.dialogs.renameFolder.label"),
      defaultValue: folder.name,
      confirmLabel: t("cases.dialogs.renameFolder.confirm"),
      cancelLabel: t("cases.dialogs.cancel"),
      validate: (v) =>
        v.trim().length === 0 ? t("cases.dialogs.renameFolder.emptyError") : null,
    });
    if (!name || name.trim() === folder.name) return;
    try {
      const r = await fetch(`/api/be/folders/${folder.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
      }
      const data = (await r.json()) as { folder: CaseFolder };
      setFolders((prev) => prev.map((f) => (f.id === folder.id ? data.folder : f)));
      toast.success(t("cases.toasts.folderRenamed"), data.folder.name);
    } catch (err) {
      toast.error(t("cases.toasts.folderRenameFailed"), err instanceof Error ? err.message : undefined);
    }
  }, [t]);

  const deleteFolder = useCallback(
    async (folder: CaseFolder) => {
      const ok = await customConfirm({
        title: t("cases.dialogs.deleteFolder.title", { name: folder.name }),
        body: t("cases.dialogs.deleteFolder.body"),
        confirmLabel: t("cases.dialogs.deleteFolder.confirm"),
        cancelLabel: t("cases.dialogs.cancel"),
        variant: "danger",
      });
      if (!ok) return;
      try {
        const r = await fetch(`/api/be/folders/${folder.id}`, { method: "DELETE" });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
        }
        const removed = descendantIds(folders, folder.id);
        setFolders((prev) => prev.filter((f) => !removed.has(f.id)));
        if (currentFolder != null && removed.has(currentFolder)) {
          setCurrentFolder(folder.parent_id);
        }
        toast.success(t("cases.toasts.folderDeleted"), folder.name);
        await fetchCases();
      } catch (err) {
        toast.error(t("cases.toasts.folderDeleteFailed"), err instanceof Error ? err.message : undefined);
      }
    },
    [folders, currentFolder, fetchCases, t]
  );

  const moveCase = useCallback(
    async (caseId: number, folder_id: FolderId) => {
      try {
        const r = await fetch(`/api/be/cases/${caseId}/move`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ folder_id }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
        }
        const dest =
          folder_id == null
            ? t("cases.modals.move.root")
            : folderById.get(folder_id)?.name ?? `#${folder_id}`;
        toast.success(t("cases.toasts.caseMoved"), t("cases.toasts.caseMovedTo", { dest }));
        await fetchCases();
      } catch (err) {
        toast.error(t("cases.toasts.caseMoveFailed"), err instanceof Error ? err.message : undefined);
      }
    },
    [folderById, fetchCases, t]
  );

  const renameCase = useCallback(
    async (c: CaseSummary) => {
      const next = await customPrompt({
        title: t("cases.dialogs.renameCase.title"),
        body: t("cases.dialogs.renameCase.body"),
        label: t("cases.dialogs.renameCase.label"),
        defaultValue: c.title.split(" · ")[0] ?? c.title,
        confirmLabel: t("cases.dialogs.renameCase.confirm"),
        cancelLabel: t("cases.dialogs.cancel"),
        validate: (v) =>
          v.trim().length === 0 ? t("cases.dialogs.renameCase.emptyError") : null,
      });
      if (!next) return;
      const suffixIdx = c.title.indexOf(" · ");
      const suffix = suffixIdx >= 0 ? c.title.slice(suffixIdx) : "";
      const newTitle = `${next.trim()}${suffix}`;
      if (newTitle === c.title) return;
      try {
        const r = await fetch(`/api/be/cases/${c.id}`, {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ title: newTitle }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
        }
        toast.success(t("cases.toasts.caseRenamed"), newTitle);
        await fetchCases();
      } catch (err) {
        toast.error(t("cases.toasts.caseRenameFailed"), err instanceof Error ? err.message : undefined);
      }
    },
    [fetchCases, t]
  );

  const deleteCase = useCallback(
    async (c: CaseSummary) => {
      const ok = await customConfirm({
        title: t("cases.dialogs.deleteCase.title", { title: c.title }),
        body: t("cases.dialogs.deleteCase.body"),
        confirmLabel: t("cases.dialogs.deleteCase.confirm"),
        cancelLabel: t("cases.dialogs.cancel"),
        variant: "danger",
      });
      if (!ok) return;
      try {
        const r = await fetch(`/api/be/cases/${c.id}`, { method: "DELETE" });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
        }
        toast.success(t("cases.toasts.caseDeleted"), c.title);
        await fetchCases();
      } catch (err) {
        toast.error(t("cases.toasts.caseDeleteFailed"), err instanceof Error ? err.message : undefined);
      }
    },
    [fetchCases, t]
  );

  // -------------------------------------------------------------------------
  // Drag & drop wiring (table row → folder card)
  // -------------------------------------------------------------------------

  const handleDragStart =
    (caseId: number) => (e: React.DragEvent<HTMLTableRowElement>) => {
      setDragCaseId(caseId);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/x-verda-case-id", String(caseId));
    };
  const handleDragEnd = () => {
    setDragCaseId(null);
    setDropTargetFolderId(null);
  };

  const handleFolderDragOver =
    (folder_id: FolderId) => (e: React.DragEvent) => {
      if (dragCaseId == null) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      setDropTargetFolderId(folder_id);
    };

  const handleFolderDrop =
    (folder_id: FolderId) => (e: React.DragEvent) => {
      e.preventDefault();
      const id = Number(e.dataTransfer.getData("text/x-verda-case-id")) || dragCaseId;
      setDropTargetFolderId(null);
      setDragCaseId(null);
      if (!id) return;
      void moveCase(id, folder_id);
    };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const breadcrumb = currentFolder == null ? [] : pathToRoot(folders, currentFolder);
  const headingLabel =
    currentFolder == null
      ? t("cases.allCases")
      : breadcrumb[breadcrumb.length - 1]?.name ?? "";
  const tableCaption =
    currentFolder == null
      ? t("cases.tableCaption.root")
      : t("cases.tableCaption.in", { name: headingLabel });

  return (
    <div className="grid gap-6">
      {/* Breadcrumb — plain text, no surrounding card. "All cases" link
          on the left renders only when we're inside a folder, so the page
          doesn't show a self-referential link at the root view. */}
      {breadcrumb.length > 0 ? (
        <Breadcrumb
          crumbs={breadcrumb}
          onJump={(id) => setCurrentFolder(id)}
          onRename={renameFolder}
          onDelete={deleteFolder}
          onNewSubfolder={(f) => createFolder(f.id)}
        />
      ) : null}

      {/* Folder section */}
      <section className="grid gap-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.18em] text-ink/45">
            {currentFolder == null
              ? t("cases.folders.headingRoot")
              : t("cases.folders.headingIn", { name: headingLabel })}
            <InfoTip
              side="right"
              content={(() => {
                // Bold the "drag any case row" phrase wherever it appears in
                // the localised tooltip — split on the bolded phrase the
                // catalog provides separately.
                const tip = t("cases.folders.tooltip");
                const bold = t("cases.folders.tooltipDragBold");
                if (!tip.includes(bold)) return <>{tip}</>;
                const parts = tip.split(bold);
                return (
                  <>
                    {parts.map((p, i) => (
                      <span key={i}>
                        {p}
                        {i < parts.length - 1 ? (
                          <strong className="text-ink">{bold}</strong>
                        ) : null}
                      </span>
                    ))}
                  </>
                );
              })()}
            />
          </h2>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => createFolder(currentFolder)}>
              <FolderIcon className="h-4 w-4" /> {t("cases.folders.newButton")}
            </Button>
            {hasOverflow && !showAllFolders ? (
              <button
                onClick={() => setShowAllFolders(true)}
                className="inline-flex items-center gap-1 text-xs font-medium text-ink/70 underline-offset-4 hover:text-ink hover:underline"
              >
                <FolderIcon className="h-3.5 w-3.5" />
                {t("cases.folders.viewAll")}
              </button>
            ) : null}
            {showAllFolders && hasOverflow ? (
              <button
                onClick={() => setShowAllFolders(false)}
                className="inline-flex items-center gap-1 text-xs font-medium text-ink/70 underline-offset-4 hover:text-ink hover:underline"
              >
                {t("cases.folders.collapse")}
              </button>
            ) : null}
          </div>
        </div>

        {visibleFolders.length === 0 ? (
          <div className="rounded-xl border border-dashed border-ink/15 bg-paper-deep/40 px-4 py-8 text-center text-sm text-ink/55">
            {currentFolder == null
              ? t("cases.folders.emptyRoot")
              : t("cases.folders.emptySubfolder")}
          </div>
        ) : (
          <ul className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
            {cappedFolders.map((f) => {
              const subFolderCount = folders.filter((x) => x.parent_id === f.id).length;
              // Cases visible on the current page that live in this folder.
              // Gives a quick "has files?" hint without an extra fetch — the
              // visual is intentionally a hint, not an exact count.
              const localCaseCount = list.cases.filter(
                (c) => c.folder_id === f.id
              ).length;
              const hasContents = subFolderCount > 0 || localCaseCount > 0;
              const isDropTarget = dropTargetFolderId === f.id;
              return (
                <li
                  key={f.id}
                  onDragOver={handleFolderDragOver(f.id)}
                  onDragLeave={() => setDropTargetFolderId(null)}
                  onDrop={handleFolderDrop(f.id)}
                  className={
                    // Light, transparent-whitish tile sized just enough to
                    // contain the icon + caption. The icon dominates; the
                    // tile is decoration, not chrome. The tile is capped at
                    // 80% of its grid cell so the visual reads as a
                    // thumbnail rather than filling every cell edge-to-edge.
                    "group relative mx-auto grid w-4/5 gap-1.5 rounded-lg bg-white/50 px-2 py-2 backdrop-blur-sm transition " +
                    (isDropTarget
                      ? "ring-2 ring-gold bg-gold-soft/60"
                      : "hover:bg-white/80")
                  }
                >
                  <button
                    onClick={() => {
                      setCurrentFolder(f.id);
                      setShowAllFolders(false);
                    }}
                    className="flex justify-center rounded-md py-1 text-ink focus-ring"
                    title={t("cases.folders.openTitle", { name: f.name })}
                  >
                    <FolderTileIcon filled={hasContents} className="h-20 w-20" />
                  </button>
                  <div className="flex items-start justify-between gap-1.5 min-w-0">
                    <button
                      onClick={() => {
                        setCurrentFolder(f.id);
                        setShowAllFolders(false);
                      }}
                      className="min-w-0 flex-1 text-left focus-ring rounded"
                      title={f.name}
                    >
                      <span className="block truncate text-sm font-medium text-ink">
                        {f.name}
                      </span>
                      <span className="block text-[10px] text-ink/45 mono">
                        {subFolderCount > 0
                          ? pluralRules.select(subFolderCount) === "one"
                            ? t("cases.folders.subFoldersOne")
                            : t("cases.folders.subFoldersOther", { count: subFolderCount })
                          : t("cases.folders.open")}
                      </span>
                    </button>
                    <ActionsMenu
                      align="right"
                      buttonLabel={t("cases.folders.actionsLabel", { name: f.name })}
                      items={[
                        {
                          key: "open",
                          label: t("cases.folders.actions.open"),
                          icon: <FolderIcon open className="h-4 w-4" />,
                          onSelect: () => setCurrentFolder(f.id),
                        },
                        {
                          key: "subfolder",
                          label: t("cases.folders.actions.subfolder"),
                          icon: <PlusIcon />,
                          onSelect: () => createFolder(f.id),
                          divider: true,
                        },
                        {
                          key: "rename",
                          label: t("cases.folders.actions.rename"),
                          icon: <PencilIcon />,
                          onSelect: () => renameFolder(f),
                        },
                        {
                          key: "delete",
                          label: t("cases.folders.actions.delete"),
                          icon: <TrashIcon />,
                          danger: true,
                          onSelect: () => deleteFolder(f),
                        },
                      ]}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Strip above the table — caption on the left + plain "All cases →"
          link on the far right. Only shown when we're inside a folder so
          a "All cases" link at the root doesn't link to itself. */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] uppercase tracking-[0.16em] text-ink/45">
        <span className="inline-flex items-center gap-1.5">
          {tableCaption}
          <InfoTip
            side="right"
            content={
              <>
                {t("cases.tableCaption.tooltipPrefix")}{" "}
                <strong className="text-ink">{tableCaption.toLowerCase()}</strong>.
                {" "}{t("cases.tableCaption.tooltipSuffix")}
              </>
            }
          />
        </span>
        {currentFolder != null ? (
          <button
            onClick={() => setCurrentFolder(null)}
            className="text-link normal-case tracking-normal"
          >
            {t("cases.allCases")} <span aria-hidden="true">→</span>
          </button>
        ) : null}
      </div>

      {/* Cases table */}
      <CasesTable
        cases={list.cases}
        loading={loading}
        folderById={folderById}
        folders={folders}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onMoveTo={moveCase}
        onRename={renameCase}
        onDelete={deleteCase}
      />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={list.totalPages}
        total={list.total}
        perPage={PER_PAGE}
        onPage={setPage}
      />

      <button
        onClick={async () => {
          await Promise.all([fetchFolders(), fetchCases()]);
          router.refresh();
        }}
        className="self-end text-[11px] text-ink/45 hover:text-ink underline-offset-2 hover:underline"
      >
        {t("cases.refresh")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Breadcrumb({
  crumbs,
  onJump,
  onRename,
  onDelete,
  onNewSubfolder,
}: {
  crumbs: CaseFolder[];
  onJump: (id: number | null) => void;
  onRename: (f: CaseFolder) => void;
  onDelete: (f: CaseFolder) => void;
  onNewSubfolder: (f: CaseFolder) => void;
}) {
  const t = useT();
  const last = crumbs[crumbs.length - 1];
  return (
    <nav className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <ol className="flex flex-wrap items-center gap-1 text-ink/60">
        <li>
          <button
            onClick={() => onJump(null)}
            className="text-link"
          >
            {t("cases.breadcrumb.allCases")}
          </button>
        </li>
        {crumbs.map((c, i) => (
          <li key={c.id} className="flex items-center gap-1">
            <span className="text-ink/30">/</span>
            <button
              onClick={() => onJump(c.id)}
              className={
                "inline-flex items-center gap-1 rounded px-1 py-0.5 " +
                (i === crumbs.length - 1
                  ? "font-semibold text-ink"
                  : "hover:text-ink hover:underline underline-offset-2")
              }
            >
              <FolderIcon open={i === crumbs.length - 1} className="h-3.5 w-3.5" />
              {c.name}
            </button>
          </li>
        ))}
      </ol>
      {last ? (
        <ActionsMenu
          buttonLabel={t("cases.breadcrumb.actionsLabel", { name: last.name })}
          items={[
            {
              key: "subfolder",
              label: t("cases.folders.actions.subfolder"),
              icon: <PlusIcon />,
              onSelect: () => onNewSubfolder(last),
              divider: true,
            },
            {
              key: "rename",
              label: t("cases.folders.actions.renameFolder"),
              icon: <PencilIcon />,
              onSelect: () => onRename(last),
            },
            {
              key: "delete",
              label: t("cases.folders.actions.delete"),
              icon: <TrashIcon />,
              danger: true,
              onSelect: () => onDelete(last),
            },
          ]}
        />
      ) : null}
    </nav>
  );
}

function CasesTable({
  cases,
  loading,
  folderById,
  folders,
  onDragStart,
  onDragEnd,
  onMoveTo,
  onRename,
  onDelete,
}: {
  cases: CaseSummary[];
  loading: boolean;
  folderById: Map<number, CaseFolder>;
  folders: CaseFolder[];
  onDragStart: (id: number) => (e: React.DragEvent<HTMLTableRowElement>) => void;
  onDragEnd: () => void;
  onMoveTo: (caseId: number, folder: number | null) => void;
  onRename: (c: CaseSummary) => void;
  onDelete: (c: CaseSummary) => void;
}) {
  const t = useT();
  if (!loading && cases.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-ink/15 bg-paper-deep/30 px-6 py-10 text-center text-sm text-ink/55">
        {t("cases.empty")}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-ink/10 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-paper-deep/40 text-[10px] uppercase tracking-[0.14em] text-ink/55">
          <tr>
            <th className="w-10 px-3 py-2"></th>
            <th className="px-3 py-2">{t("cases.table.title")}</th>
            <th className="px-3 py-2 hidden sm:table-cell">{t("cases.table.track")}</th>
            <th className="px-3 py-2 hidden lg:table-cell">{t("cases.table.files")}</th>
            <th className="px-3 py-2 hidden lg:table-cell">
              <span className="inline-flex items-center gap-1.5">
                {t("cases.table.updated")}
                <InfoTip
                  side="bottom"
                  content={t("cases.table.updatedTooltip")}
                />
              </span>
            </th>
            <th className="px-3 py-2">{t("cases.table.status")}</th>
            <th className="px-3 py-2 text-right">{t("cases.table.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <CaseRow
              key={c.id}
              c={c}
              folderById={folderById}
              folders={folders}
              onDragStart={onDragStart(c.id)}
              onDragEnd={onDragEnd}
              onMoveTo={(folder_id) => onMoveTo(c.id, folder_id)}
              onRename={() => onRename(c)}
              onDelete={() => onDelete(c)}
            />
          ))}
          {loading && cases.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-ink/50 text-sm">
                {t("cases.table.loading")}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function CaseRow({
  c,
  folderById: _folderById,
  folders,
  onDragStart,
  onDragEnd,
  onMoveTo,
  onRename,
  onDelete,
}: {
  c: CaseSummary;
  folderById: Map<number, CaseFolder>;
  folders: CaseFolder[];
  onDragStart: (e: React.DragEvent<HTMLTableRowElement>) => void;
  onDragEnd: () => void;
  onMoveTo: (folder_id: number | null) => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const t = useT();
  const [exportOpen, setExportOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  // Generation gates the export modal: the case is exportable only when
  // a run has finished (latest_run_id present means at least one run).
  const generated = !!c.latest_run_id;

  const items: ActionItem[] = [
    {
      key: "open",
      label: t("cases.row.open"),
      icon: <OpenIcon />,
      onSelect: () => {
        window.location.href = `/cases/${c.id}`;
      },
    },
    {
      key: "rename",
      label: t("cases.row.rename"),
      icon: <PencilIcon />,
      onSelect: onRename,
    },
    {
      key: "move",
      label: t("cases.row.moveTo"),
      icon: <FolderMoveIcon />,
      onSelect: () => setMoveOpen(true),
      divider: true,
    },
    {
      key: "export",
      label: generated ? t("cases.row.exportReady") : t("cases.row.exportNeedsGenerate"),
      icon: <DownloadIcon />,
      disabled: !generated,
      disabledHint: t("cases.row.exportDisabledHint"),
      onSelect: () => setExportOpen(true),
      divider: true,
    },
    {
      key: "delete",
      label: t("cases.row.delete"),
      icon: <TrashIcon />,
      danger: true,
      onSelect: onDelete,
    },
  ];

  return (
    <tr
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className="group cursor-grab border-t border-ink/8 transition hover:bg-paper-deep/40 active:cursor-grabbing"
    >
      <td className="px-3 py-3 align-top">
        <span className="mono text-[10px] text-ink/40">#{c.id}</span>
      </td>
      <td className="px-3 py-3 align-top">
        <Link
          href={`/cases/${c.id}`}
          className="font-medium text-ink hover:text-rust"
        >
          {c.title}
        </Link>
        {c.description ? (
          <p className="mt-0.5 line-clamp-1 text-xs text-ink/55">{c.description}</p>
        ) : null}
      </td>
      <td className="px-3 py-3 align-top text-xs text-ink/65 hidden sm:table-cell">
        <span className="mono">{c.legal_track}</span>
      </td>
      <td className="px-3 py-3 align-top text-xs text-ink/65 hidden lg:table-cell">
        {c.file_count ?? 0}
      </td>
      <td className="px-3 py-3 align-top text-xs hidden lg:table-cell">
        <DateText iso={c.updated_at ?? c.created_at} variant="datetime" />
      </td>
      <td className="px-3 py-3 align-top">
        <Badge variant={STATUS_TONE[c.status] ?? "paper"}>{c.status}</Badge>
      </td>
      <td className="px-3 py-3 align-top">
        <div className="flex items-center justify-end gap-1">
          <ActionsMenu items={items} />
        </div>
        {moveOpen ? (
          <MoveCaseModal
            caseId={c.id}
            currentFolderId={c.folder_id ?? null}
            folders={folders}
            onClose={() => setMoveOpen(false)}
            onMove={(target) => {
              setMoveOpen(false);
              onMoveTo(target);
            }}
          />
        ) : null}
        {exportOpen ? (
          <ExportModal
            caseId={c.id}
            caseTitle={c.title}
            onClose={() => setExportOpen(false)}
          />
        ) : null}
      </td>
    </tr>
  );
}

const STATUS_TONE: Record<string, "gold" | "fern" | "rust" | "ink"> = {
  intake: "gold",
  generated: "fern",
  filed: "ink",
};

// ---------------------------------------------------------------------------
// Modals
// ---------------------------------------------------------------------------

function MoveCaseModal({
  caseId,
  currentFolderId,
  folders,
  onClose,
  onMove,
}: {
  caseId: number;
  currentFolderId: number | null;
  folders: CaseFolder[];
  onClose: () => void;
  onMove: (folderId: number | null) => void;
}) {
  const t = useT();
  const ref = useRef<HTMLDivElement | null>(null);
  const { closing, trigger: animatedClose } = useSheetExit(onClose, 220);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") animatedClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [animatedClose]);
  return (
    <div
      role="dialog"
      aria-modal="true"
      data-overlay
      data-state={closing ? "closing" : "open"}
      className="fixed inset-0 z-[180] flex items-center justify-center bg-ink/40 px-4 backdrop-blur-sm"
      onClick={(e) => {
        if (!ref.current?.contains(e.target as Node)) animatedClose();
      }}
    >
      <div
        ref={ref}
        onClick={(e) => e.stopPropagation()}
        data-modal="sheet"
        data-state={closing ? "closing" : "open"}
        className="w-full max-w-md rounded-2xl border border-ink/10 bg-paper p-5 shadow-2xl shadow-ink/30"
      >
        <header className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[10px] uppercase tracking-[0.16em] text-ink/45">
              {t("cases.modals.move.kicker", { id: caseId })}
            </p>
            <h2 className="serif mt-1 text-lg font-semibold text-ink">
              {t("cases.modals.move.title")}
            </h2>
          </div>
          <button
            onClick={animatedClose}
            aria-label={t("cases.modals.move.close")}
            className="rounded p-1 text-ink/45 hover:bg-ink/5 hover:text-ink"
          >
            ×
          </button>
        </header>
        <ul className="mt-3 max-h-[60vh] overflow-y-auto rounded-lg border border-ink/10 bg-white">
          <li>
            <button
              onClick={() => onMove(null)}
              className={
                "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-paper-deep/60 " +
                (currentFolderId == null ? "text-ink font-medium" : "text-ink/70")
              }
            >
              <span className="grid h-5 w-5 place-items-center text-ink/45">·</span>
              {t("cases.modals.move.root")}
            </button>
          </li>
          {folders
            .slice()
            .sort((a, b) =>
              pathToRoot(folders, a.id).map((f) => f.name).join("/").localeCompare(
                pathToRoot(folders, b.id).map((f) => f.name).join("/")
              )
            )
            .map((f) => {
              const path = pathToRoot(folders, f.id).map((p) => p.name).join(" / ");
              return (
                <li key={f.id}>
                  <button
                    onClick={() => onMove(f.id)}
                    className={
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-paper-deep/60 " +
                      (currentFolderId === f.id ? "text-ink font-medium" : "text-ink/70")
                    }
                  >
                    <FolderIcon className="h-4 w-4 shrink-0 text-ink/55" />
                    <span className="truncate" title={path}>{path}</span>
                  </button>
                </li>
              );
            })}
        </ul>
      </div>
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  perPage,
  onPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
}) {
  const t = useT();
  if (totalPages <= 1) return null;
  const start = total === 0 ? 0 : (page - 1) * perPage + 1;
  const end = Math.min(total, page * perPage);
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink/55"
    >
      <span>{t("cases.pagination.showing", { start, end, total })}</span>
      <div className="inline-flex items-center gap-1">
        <button
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-md border border-ink/12 bg-white px-2 py-1 text-ink/65 disabled:opacity-40"
        >
          {t("cases.pagination.prev")}
        </button>
        {pageNumbers(page, totalPages).map((p, i) =>
          p === "ellipsis" ? (
            <span key={`e-${i}`} className="px-1 text-ink/40">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={
                "rounded-md px-2.5 py-1 transition " +
                (p === page
                  ? "bg-ink text-paper"
                  : "border border-ink/12 bg-white text-ink/65 hover:border-ink/30 hover:text-ink")
              }
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="rounded-md border border-ink/12 bg-white px-2 py-1 text-ink/65 disabled:opacity-40"
        >
          {t("cases.pagination.next")}
        </button>
      </div>
    </nav>
  );
}

function pageNumbers(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | "ellipsis")[] = [];
  out.push(1);
  if (current > 4) out.push("ellipsis");
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) {
    out.push(p);
  }
  if (current < total - 3) out.push("ellipsis");
  out.push(total);
  return out;
}

// ---------------------------------------------------------------------------
// Export modal — gated on completed generation
// ---------------------------------------------------------------------------

// Export targets — labels resolved from the catalog at render so each
// language has its own copy. Keys are stable for backend payloads.
const EXPORT_TARGET_KEYS = ["zip", "encrypted", "docker", "usb"] as const;
type ExportTargetKey = (typeof EXPORT_TARGET_KEYS)[number];

function ExportModal({
  caseId,
  caseTitle,
  onClose,
}: {
  caseId: number;
  caseTitle: string;
  onClose: () => void;
}) {
  const t = useT();
  const [busy, setBusy] = useState<string | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [pickedEncrypted, setPickedEncrypted] = useState(false);

  const ref = useRef<HTMLDivElement | null>(null);
  const { closing, trigger: animatedClose } = useSheetExit(onClose, 220);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") animatedClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [animatedClose]);

  const filenameFor = (target: string) => {
    if (target === "zip") return `wakili_case_${caseId}.zip`;
    if (target === "encrypted") return `wakili_case_${caseId}_encrypted.zip`;
    if (target === "docker") return `wakili_case_${caseId}_docker.tar.gz`;
    return `wakili_case_${caseId}_usb.zip`;
  };

  const runExport = async (target: ExportTargetKey) => {
    if (target === "encrypted" && passphrase.length < 8) {
      setPickedEncrypted(true);
      return;
    }
    setBusy(target);
    try {
      const res = await fetch(`/api/be/cases/${caseId}/export`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target,
          ...(target === "encrypted" ? { passphrase } : {}),
        }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          detail = body.detail ?? detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filenameFor(target);
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready", filenameFor(target));
      animatedClose();
    } catch (err) {
      toast.error("Export failed", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      data-overlay
      data-state={closing ? "closing" : "open"}
      className="fixed inset-0 z-[180] flex items-center justify-center bg-ink/40 px-4 backdrop-blur-sm"
      onClick={(e) => {
        if (!ref.current?.contains(e.target as Node)) animatedClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={ref}
        data-modal="sheet"
        data-state={closing ? "closing" : "open"}
        className="w-full max-w-lg rounded-2xl border border-ink/10 bg-paper p-5 shadow-2xl shadow-ink/30"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[10px] uppercase tracking-[0.16em] text-ink/45">
              {t("cases.modals.export.kicker", { id: caseId })}
            </p>
            <h2 className="serif mt-1 text-lg font-semibold text-ink">{caseTitle}</h2>
            <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-ink/60">
              {t("cases.modals.export.status")}
              <InfoTip
                side="right"
                content={t("cases.modals.export.statusTooltip")}
              />
            </p>
          </div>
          <button
            onClick={animatedClose}
            className="rounded p-1 text-ink/45 hover:bg-ink/5 hover:text-ink"
            aria-label={t("cases.modals.export.close")}
          >
            ×
          </button>
        </div>

        <ul className="mt-4 grid gap-2">
          {EXPORT_TARGET_KEYS.map((k) => (
            <li key={k}>
              <button
                onClick={() => runExport(k)}
                disabled={busy !== null}
                className={
                  "group flex w-full items-center justify-between gap-3 rounded-lg border bg-white px-4 py-3 text-left transition " +
                  (busy === k
                    ? "border-gold ring-2 ring-gold/40"
                    : "border-ink/10 hover:border-gold/45")
                }
              >
                <span>
                  <span className="block text-sm font-medium text-ink">
                    {t(`cases.modals.export.targets.${k}.label`)}
                  </span>
                  <span className="block text-[11px] text-ink/55">
                    {t(`cases.modals.export.targets.${k}.sub`)}
                  </span>
                </span>
                <span className="mono text-[11px] text-ink/45 group-hover:text-ink/70">
                  {busy === k
                    ? t("cases.modals.export.building")
                    : t("cases.modals.export.download")}
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div
          className={
            "mt-3 grid gap-1 rounded-lg border px-3 py-2 transition " +
            (pickedEncrypted
              ? "border-gold bg-gold-soft/30"
              : "border-ink/10 bg-white")
          }
        >
          <label
            htmlFor="export-passphrase"
            className="text-[10px] uppercase tracking-[0.14em] text-ink/55"
          >
            {t("cases.modals.export.passphraseLabel")}
          </label>
          <input
            id="export-passphrase"
            type="password"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            placeholder={t("cases.modals.export.passphrasePlaceholder")}
            className="bg-transparent text-sm outline-none"
          />
          {pickedEncrypted && passphrase.length < 8 ? (
            <p className="text-[11px] text-rust">
              {t("cases.modals.export.passphraseError")}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
