"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "./ui/button";
import { toast } from "@/lib/toast";
import { confirm as customConfirm } from "@/lib/dialog";
import { useT, useIntl } from "@/lib/i18n/provider";

// Browsers expose folder drops via the legacy webkitGetAsEntry tree, not the
// flat DataTransfer.files list (a folder drop yields zero files). We walk the
// FileSystemEntry tree to collect every File with a relative path so the user
// can drop a whole case directory.
type FsFileEntry = { isFile: true; isDirectory: false; name: string; fullPath: string; file: (cb: (f: File) => void, err?: (e: unknown) => void) => void };
type FsDirectoryEntry = { isFile: false; isDirectory: true; name: string; fullPath: string; createReader: () => { readEntries: (cb: (entries: FsEntry[]) => void, err?: (e: unknown) => void) => void } };
type FsEntry = FsFileEntry | FsDirectoryEntry;

async function readDirectory(dir: FsDirectoryEntry): Promise<FsEntry[]> {
  const reader = dir.createReader();
  const all: FsEntry[] = [];
  // readEntries returns at most ~100 per call; loop until empty.
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const batch = await new Promise<FsEntry[]>((resolve, reject) =>
      reader.readEntries(resolve, reject)
    );
    if (!batch.length) return all;
    all.push(...batch);
  }
}

async function entryToFiles(entry: FsEntry): Promise<File[]> {
  if (entry.isFile) {
    return [
      await new Promise<File>((resolve, reject) =>
        entry.file(
          (f) => {
            // Preserve relative path so multiple files with the same name can
            // coexist (Verda stores `original_name` and dedupes by sha256).
            const tagged = new File([f], entry.fullPath.replace(/^\//, "") || f.name, {
              type: f.type,
              lastModified: f.lastModified,
            });
            resolve(tagged);
          },
          reject
        )
      ),
    ];
  }
  const children = await readDirectory(entry);
  const nested = await Promise.all(children.map(entryToFiles));
  return nested.flat();
}

async function collectFromDataTransfer(dt: DataTransfer): Promise<File[]> {
  // 1) Walk webkitGetAsEntry for directory support. We type-erase to avoid a
  //    FileSystemEntry vs FsEntry conflict in lib.dom.d.ts.
  const items = Array.from(dt.items ?? []);
  const entries: FsEntry[] = [];
  for (const it of items) {
    const getEntry = (it as unknown as { webkitGetAsEntry?: () => unknown }).webkitGetAsEntry;
    if (typeof getEntry === "function") {
      const entry = getEntry.call(it) as FsEntry | null;
      if (entry) entries.push(entry);
    }
  }
  if (entries.length) {
    const collected = await Promise.all(entries.map((e) => entryToFiles(e)));
    const flat = collected.flat();
    if (flat.length) return flat;
  }
  // 2) Fallback: flat file list (single-file or multi-file selection drop).
  if (dt.files && dt.files.length) return Array.from(dt.files);
  return [];
}

async function uploadFiles(caseId: number, files: File[]) {
  const fd = new FormData();
  for (const f of files) {
    // FormData accepts paths in the third arg; FastAPI keeps the basename
    // safely on the backend so a tagged path like "case/sub/foo.txt" is fine.
    fd.append("files", f, f.name);
  }
  const res = await fetch(`/api/be/cases/${caseId}/files`, { method: "POST", body: fd });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

async function postBe<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/be${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function UploadZone({ caseId, compact = false }: { caseId?: number; compact?: boolean }) {
  const t = useT();
  const { locale } = useIntl();
  const filesRef = useRef<HTMLInputElement | null>(null);
  const folderRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [hover, setHover] = useState(false);
  const [progress, setProgress] = useState<{ uploaded: number; total: number } | null>(null);
  const router = useRouter();

  async function ingest(files: File[]) {
    if (files.length === 0) {
      toast.error(t("upload.toasts.nothing"), t("upload.toasts.nothingHint"));
      return;
    }
    setBusy(true);
    setProgress({ uploaded: 0, total: files.length });
    try {
      let id = caseId;
      if (!id) {
        // Locale-aware date formatting so the auto-generated case title
        // uses the user's calendar conventions.
        const dateLabel = new Intl.DateTimeFormat(locale).format(new Date());
        const created = await postBe<{ case: { id: number } }>("/cases", {
          title: t("upload.untitledTitle", { date: dateLabel }),
          jurisdiction: "ke",
          legal_track: "article_22_petition",
          description: t("upload.untitledDescription"),
        });
        id = created.case.id;
      }
      await uploadFiles(id!, files);
      setProgress({ uploaded: files.length, total: files.length });
      await postBe(`/cases/${id}/plan`);
      const pluralKey =
        new Intl.PluralRules(locale).select(files.length) === "one"
          ? "upload.toasts.successBodyOne"
          : "upload.toasts.successBodyOther";
      toast.success(
        t("upload.toasts.successTitle"),
        t(pluralKey, { count: files.length }),
      );
      router.push(`/cases/${id}`);
      router.refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      const hint =
        msg.toLowerCase().includes("401") || msg.toLowerCase().includes("missing bearer")
          ? t("upload.toasts.uploadFailedSignedOut")
          : msg;
      toast.error(t("upload.toasts.uploadFailed"), hint);
    } finally {
      setBusy(false);
      setTimeout(() => setProgress(null), 600);
    }
  }

  // Detect whether the drop contains a folder (vs. flat files). We can't
  // call the async tree-walk here because that consumes the DataTransfer;
  // instead we peek at the items synchronously.
  function dropContainsFolder(dt: DataTransfer): boolean {
    const items = Array.from(dt.items ?? []);
    for (const it of items) {
      const getEntry = (it as unknown as { webkitGetAsEntry?: () => unknown }).webkitGetAsEntry;
      if (typeof getEntry === "function") {
        const entry = getEntry.call(it) as { isDirectory?: boolean } | null;
        if (entry?.isDirectory) return true;
      }
    }
    return false;
  }

  async function handleDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setHover(false);

    // Eagerly resolve the entries so the DataTransfer doesn't lapse while
    // we're showing the confirm dialog (Chrome invalidates DataTransferItems
    // once the drop event handler returns).
    const hasFolder = dropContainsFolder(e.dataTransfer);
    let files: File[] = [];
    try {
      files = await collectFromDataTransfer(e.dataTransfer);
    } catch (err) {
      toast.error(
        t("upload.toasts.dropFailed"),
        err instanceof Error ? err.message : t("upload.toasts.dropFailedFallback"),
      );
      return;
    }

    if (hasFolder) {
      const body =
        files.length > 0
          ? t("upload.dialogs.folderConfirm.bodyWithCount", { count: files.length })
          : t("upload.dialogs.folderConfirm.bodyNoCount");
      const ok = await customConfirm({
        title: t("upload.dialogs.folderConfirm.title"),
        body,
        confirmLabel: t("upload.dialogs.folderConfirm.confirm"),
        cancelLabel: t("upload.dialogs.cancel"),
        variant: "warning",
      });
      if (!ok) return;
    }

    await ingest(files);
  }

  async function pickFolder() {
    if (busy) return;
    const ok = await customConfirm({
      title: t("upload.dialogs.folderPick.title"),
      body: t("upload.dialogs.folderPick.body"),
      confirmLabel: t("upload.dialogs.folderPick.confirm"),
      cancelLabel: t("upload.dialogs.cancel"),
      variant: "warning",
    });
    if (!ok) return;
    folderRef.current?.click();
  }

  async function pickFiles() {
    if (busy) return;
    filesRef.current?.click();
  }

  return (
    <div className="grid gap-4">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          // Tell the browser this drop is allowed — without this the drag
          // cursor renders as a "not-allowed" icon over file inputs that
          // don't natively accept folders.
          if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
          setHover(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
          setHover(true);
        }}
        onDragLeave={() => setHover(false)}
        onDrop={handleDrop}
        className={
          "relative flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border-2 border-dashed px-6 text-center transition focus-ring " +
          (compact ? "min-h-[120px] py-5 " : "min-h-[200px] py-9 ") +
          (hover
            ? "border-gold bg-gold-soft/30"
            : "border-ink/15 bg-paper-deep/30 hover:border-ink/25")
        }
      >
        {/* Files-only input */}
        <input
          ref={filesRef}
          type="file"
          multiple
          className="sr-only"
          onChange={(e) => e.currentTarget.files && ingest(Array.from(e.currentTarget.files))}
        />
        {/* Folder-picker (Chrome/Edge/Safari TP). Falls back gracefully. */}
        <input
          ref={folderRef}
          type="file"
          // @ts-expect-error — non-standard but supported by Chromium + WebKit
          webkitdirectory=""
          directory=""
          multiple
          className="sr-only"
          onChange={(e) => e.currentTarget.files && ingest(Array.from(e.currentTarget.files))}
        />
        <div className="flex items-center gap-2 text-sm font-medium text-ink">
          <span className="grid place-items-center h-7 w-7 shrink-0 rounded-full bg-ink text-paper">↑</span>
          {busy
            ? progress
              ? t("upload.uploadingProgress", {
                  uploaded: progress.uploaded,
                  total: progress.total,
                })
              : t("upload.uploading")
            : t("upload.prompt")}
        </div>
        {!compact && (
          <p className="max-w-md text-xs text-ink/60">{t("upload.blurb")}</p>
        )}
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button
            variant="outline"
            type="button"
            size="sm"
            onClick={(e) => {
              e.preventDefault();
              pickFiles();
            }}
            disabled={busy}
          >
            {t("upload.browseFiles")}
          </Button>
          <Button
            variant="outline"
            type="button"
            size="sm"
            onClick={(e) => {
              e.preventDefault();
              pickFolder();
            }}
            disabled={busy}
          >
            {t("upload.browseFolder")}
          </Button>
        </div>
        {progress && progress.total > 0 ? (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-paper-deep">
            <div
              className="h-full bg-gold transition-all"
              style={{ width: `${(progress.uploaded / progress.total) * 100}%` }}
            />
          </div>
        ) : null}
      </label>
    </div>
  );
}
