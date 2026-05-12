"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../ui/button";
import { Card, CardBody, CardHeader } from "../ui/card";
import { Badge } from "../ui/badge";
import { EmptyState } from "../ui/empty-state";
import { toast } from "@/lib/toast";
import {
  confirm as customConfirm,
  prompt as customPrompt,
  alert as customAlert,
} from "@/lib/dialog";
import { usePermissions } from "@/components/auth/permissions-provider";
import { Permissions } from "@/lib/auth/permissions";

type Target = "zip" | "encrypted" | "docker" | "usb";

type Spec = {
  key: Target;
  name: string;
  description: string;
  contents: string[];
  command: string;
  needsPassphrase?: boolean;
  pillTone: "gold" | "fern" | "rust" | "ink" | "paper";
};

const SPECS: Spec[] = [
  {
    key: "zip",
    name: "Plain zip bundle",
    description: "All generated artifacts as a flat zip — petition, drafted motions, parser modules, JSON outputs, README.",
    contents: ["petition_draft.md", "evidence_codex.json", "evidence_parser.py", "drafted_motions/", "README.md"],
    command: "unzip wakili_case_<id>.zip -d wakili_case_<id>/",
    pillTone: "gold",
  },
  {
    key: "encrypted",
    name: "Encrypted bundle",
    description: "AES-256-GCM with scrypt KDF (N=2¹⁵). Output is a zip wrapper containing the encrypted blob, a self-contained decrypter, and a README. Decrypts with stdlib Python only.",
    contents: ["wakili_case_<id>.wakili", "decrypt.py (stdlib-only)", "README.md"],
    command: "python3 decrypt.py wakili_case_<id>.wakili",
    needsPassphrase: true,
    pillTone: "rust",
  },
  {
    key: "docker",
    name: "Self-hosted Docker viewer",
    description: "Single-file tarball — Dockerfile + standalone FastAPI mini-app + bundled case data. Build on the partner-org's infra, run anywhere Docker runs. No outbound calls.",
    contents: ["Dockerfile", "wakili_case_server/", "case_data/", "templates/", "static/styles.css", "README.md", "docker-compose.yml"],
    command: "tar xzf wakili_case_<id>_docker.tar.gz && cd wakili_case_<id> && docker compose up",
    pillTone: "fern",
  },
  {
    key: "usb",
    name: "USB-portable viewer",
    description: "Drop on a USB stick. Single-file viewer.html runs offline; wakili-launcher.py boots a localhost server with stdlib only. Includes RUN.sh / RUN.bat / Tails install notes / sha256 MANIFEST.",
    contents: ["viewer.html", "wakili-launcher.py", "RUN.sh / RUN.bat", "case_data/", "INSTALL_TAILS.md", "MANIFEST.json", "verify.sh"],
    command: "unzip wakili_case_<id>_usb.zip && cd wakili_case_<id> && ./RUN.sh   # or open viewer.html",
    pillTone: "ink",
  },
];

export function ExportPanelV2({ caseId, hasRun = true }: { caseId: number; hasRun?: boolean }) {
  const [busy, setBusy] = useState<Target | null>(null);
  const [generating, setGenerating] = useState(false);
  const [hasBundle, setHasBundle] = useState(hasRun);
  const router = useRouter();
  const { has } = usePermissions();
  const canExport = has(Permissions.ExportsBasic);
  const canExportEncrypted = has(Permissions.ExportsEncrypted);

  const generateNow = async () => {
    setGenerating(true);
    try {
      // Best-effort: ensure plan is approved, then generate. Reflect any 400
      // back to the user with a useful hint.
      const approve = await fetch(`/api/be/cases/${caseId}/plan/approve`, { method: "POST" });
      if (!approve.ok && approve.status !== 400) {
        const text = await approve.text();
        throw new Error(`Plan approval failed (${approve.status}): ${text}`);
      }
      const gen = await fetch(`/api/be/cases/${caseId}/generate`, { method: "POST" });
      if (!gen.ok) {
        const body = await gen.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `Generate failed (HTTP ${gen.status})`);
      }
      toast.success("Toolkit generated", "You can now export.");
      setHasBundle(true);
      router.refresh();
    } catch (err) {
      toast.error("Could not generate", err instanceof Error ? err.message : undefined);
    } finally {
      setGenerating(false);
    }
  };

  if (!hasBundle) {
    return (
      <div className="grid gap-4">
        <EmptyState
          title="Generate the toolkit before exporting"
          body="Exports are produced from the per-case bundle on disk. Approve the plan, then generate — the bundle ships with the petition draft, drafted motions, the Evidence Codex, the precedent list, and the parser modules. Export targets unlock as soon as the run completes."
          icon="↓"
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button onClick={generateNow} disabled={generating}>
                {generating ? "Generating…" : "Approve plan & generate"}
              </Button>
              <Link
                href={`/cases/${caseId}?view=plan`}
                className="inline-flex min-h-[40px] items-center rounded-lg border border-ink/15 bg-white px-3 py-2 text-xs text-ink/75 hover:border-ink/30 hover:text-ink focus-ring"
              >
                Open plan →
              </Link>
            </div>
          }
        />
        <p className="text-center text-[11px] text-ink/45">
          If you've already generated and you're still seeing this, your runtime
          directory may have been cleaned. Re-run from the Plan tab.
        </p>
      </div>
    );
  }

  const exportTarget = async (target: Target) => {
    let passphrase: string | null = null;
    if (target === "encrypted") {
      passphrase = await customPrompt({
        title: "Encrypted bundle passphrase",
        body:
          "Verda encrypts the bundle with AES-256-GCM (scrypt KDF, N=2¹⁵). The passphrase is the only way to decrypt it — Verda does not store it. Choose something memorable but strong, and share it through a separate channel from the bundle itself.",
        label: "Passphrase",
        placeholder: "≥ 8 characters; mix letter case + digits + a symbol",
        inputType: "password",
        confirmLabel: "Encrypt & download",
        cancelLabel: "Cancel",
        variant: "danger",
        strengthMeter: true,
        validate: (v) =>
          v.length < 8 ? "Passphrase must be at least 8 characters" : null,
      });
      if (!passphrase) return;
    } else {
      const targetCopy: Record<Target, { title: string; body: string; cta: string }> = {
        zip: {
          title: "Download zip bundle?",
          body:
            "All generated artifacts are bundled as a flat zip — petition, drafted motions, parser modules, JSON outputs, README. The zip is unencrypted; share it only over a trusted channel.",
          cta: "Download zip",
        },
        docker: {
          title: "Build a self-hosted Docker viewer?",
          body:
            "We'll emit a tar.gz containing a standalone FastAPI mini-app + bundled case data. The partner org runs `docker compose up` to serve the case viewer offline, with zero outbound calls.",
          cta: "Download tarball",
        },
        usb: {
          title: "Build a USB-portable viewer?",
          body:
            "We'll emit a zip with a single-file viewer.html, a stdlib launcher, RUN.sh / RUN.bat, and a sha256 MANIFEST. It runs on any USB stick the defender formats. No internet, no installer.",
          cta: "Download USB pack",
        },
        encrypted: { title: "", body: "", cta: "" }, // handled above
      };
      const copy = targetCopy[target];
      const ok = await customConfirm({
        title: copy.title,
        body: copy.body,
        confirmLabel: copy.cta,
        cancelLabel: "Cancel",
        variant: "info",
      });
      if (!ok) return;
    }

    setBusy(target);
    try {
      const res = await fetch(`/api/be/cases/${caseId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target,
          ...(target === "encrypted" && passphrase ? { passphrase } : {}),
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
        if (res.status === 404) {
          // The bundle was never written — fall back to the empty state so
          // the user can generate from this same panel.
          setHasBundle(false);
          throw new Error(
            "No generated bundle yet for this case. Generate the toolkit first."
          );
        }
        throw new Error(detail);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filenameFor(target, caseId);
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready", filenameFor(target, caseId));
      if (target === "encrypted") {
        await customAlert({
          title: "Bundle encrypted — keep the passphrase safe",
          body:
            "The download has started. Verda did not store the passphrase. Share it with the recipient through a separate channel from the bundle itself (e.g. SMS to the phone, where the bundle goes by USB).",
          variant: "success",
          confirmLabel: "Got it",
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      await customAlert({
        title: "Export failed",
        body: msg,
        variant: "danger",
      });
      toast.error("Export failed", msg);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-4">
      <Card tone="deep">
        <CardBody className="!py-3">
          <p className="text-sm text-ink/70">
            Verda emits real, runnable artifacts. The encrypted, Docker, and USB
            targets are not manifests — they are deliverables a defender can run
            today, with no outbound network calls and no telemetry.
          </p>
        </CardBody>
      </Card>

      <ul className="grid gap-3 lg:grid-cols-2">
        {SPECS.map((s) => (
          <Card key={s.key}>
            <CardHeader
              title={
                <span className="flex flex-wrap items-center gap-2">
                  {s.name}
                  <Badge variant={s.pillTone}>{s.key}</Badge>
                </span>
              }
              right={(() => {
                const blocked =
                  !canExport ||
                  (s.key === "encrypted" && !canExportEncrypted);
                const blockReason = !canExport
                  ? "Your role can't export bundles."
                  : s.key === "encrypted" && !canExportEncrypted
                  ? "Encrypted exports are restricted to the lawyer role."
                  : undefined;
                return (
                  <Button
                    size="sm"
                    onClick={() => exportTarget(s.key)}
                    disabled={busy !== null || blocked}
                    title={blockReason}
                  >
                    {busy === s.key ? "Exporting…" : "Export"}
                  </Button>
                );
              })()}
            />
            <CardBody className="!pt-3 grid gap-3">
              <p className="text-sm text-ink/70 leading-relaxed pretty">{s.description}</p>
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-ink/45 mb-1">What you get</p>
                <ul className="grid gap-0.5 text-xs">
                  {s.contents.map((c) => (
                    <li key={c} className="mono text-ink/60 truncate">— {c}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-ink/45 mb-1">Run command</p>
                <code className="mono block break-all rounded-md border border-ink/8 bg-paper-deep/40 px-2 py-1.5 text-[11px] text-ink/80">
                  {s.command}
                </code>
              </div>
              {s.needsPassphrase ? (
                <p className="rounded-md border border-rust/25 bg-rust/8 px-2.5 py-2 text-[11px] text-rust">
                  You'll be prompted for a passphrase when you click Export.
                  Verda does not store it.
                </p>
              ) : null}
            </CardBody>
          </Card>
        ))}
      </ul>
    </div>
  );
}

function filenameFor(target: Target, caseId: number): string {
  switch (target) {
    case "zip":
      return `wakili_case_${caseId}.zip`;
    case "encrypted":
      return `wakili_case_${caseId}_encrypted.zip`;
    case "docker":
      return `wakili_case_${caseId}_docker.tar.gz`;
    case "usb":
      return `wakili_case_${caseId}_usb.zip`;
  }
}

