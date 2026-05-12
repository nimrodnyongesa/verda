"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { UserProfile } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { DateText } from "./ui/date-text";
import { InfoTip } from "./ui/info-tip";
import { toast } from "@/lib/toast";
import { confirm as customConfirm } from "@/lib/dialog";
import { emitProfileUpdated } from "@/lib/profile-events";
import { useT } from "@/lib/i18n/provider";

const ROLE_TONE: Record<string, "ink" | "gold" | "fern" | "rust" | "paper"> = {
  admin: "ink",
  lawyer: "gold",
  paralegal: "fern",
  viewer: "paper",
  auditor: "rust",
  anonymous: "paper",
};

// Permission → catalog-key mapping. The matrix is intentionally explicit
// (rather than parsed from the permission string) so the lawyer sees what
// the verb actually unlocks. Labels and hints resolve at render through
// `t()` so each language ships its own copy of the policy.
const PERMISSION_KEYS: Record<string, string> = {
  "cases:read":         "casesRead",
  "cases:create":       "casesCreate",
  "cases:write":        "casesWrite",
  "cases:delete":       "casesDelete",
  "cases:share":        "casesShare",
  "plan:approve":       "planApprove",
  "generation:run":     "generationRun",
  "exports:basic":      "exportsBasic",
  "exports:encrypted":  "exportsEncrypted",
  "audit:case":         "auditCase",
  "audit:global":       "auditGlobal",
  "users:read":         "usersRead",
  "users:manage":       "usersManage",
};

export function ProfilePageClient({
  initialProfile,
}: {
  initialProfile: UserProfile;
}) {
  const t = useT();
  const [profile, setProfile] = useState<UserProfile>(initialProfile);
  const [displayName, setDisplayName] = useState(initialProfile.display_name);
  const [bio, setBio] = useState(initialProfile.bio);
  const [savingProfile, setSavingProfile] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const dirty = useMemo(
    () => displayName !== profile.display_name || bio !== (profile.bio ?? ""),
    [displayName, bio, profile.display_name, profile.bio]
  );

  const initial = (profile.display_name || profile.sub).slice(0, 1).toUpperCase();
  const avatarUrl = profile.has_avatar
    ? `/api/be/me/profile/avatar?v=${profile.avatar_version}`
    : null;

  async function saveProfile() {
    setSavingProfile(true);
    try {
      const res = await fetch("/api/be/me/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          display_name: displayName.trim() || null,
          bio: bio.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { profile: UserProfile };
      setProfile(data.profile);
      setDisplayName(data.profile.display_name);
      setBio(data.profile.bio ?? "");
      emitProfileUpdated(data.profile);
      toast.success(t("profile.toasts.saved"));
    } catch (err) {
      toast.error(t("profile.toasts.saveFailed"), err instanceof Error ? err.message : undefined);
    } finally {
      setSavingProfile(false);
    }
  }

  async function uploadAvatar(file: File) {
    const fd = new FormData();
    fd.append("avatar", file, file.name);
    setUploading(true);
    try {
      const res = await fetch("/api/be/me/profile/avatar", {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { profile: UserProfile };
      setProfile(data.profile);
      emitProfileUpdated(data.profile);
      toast.success(t("profile.toasts.avatarUploaded"));
    } catch (err) {
      toast.error(t("profile.toasts.avatarUploadFailed"), err instanceof Error ? err.message : undefined);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function removeAvatar() {
    const ok = await customConfirm({
      title: t("profile.avatar.removeTitle"),
      body: t("profile.avatar.removeBody"),
      confirmLabel: t("profile.avatar.removeConfirm"),
      cancelLabel: t("profile.avatar.removeCancel"),
      variant: "warning",
    });
    if (!ok) return;
    try {
      const res = await fetch("/api/be/me/profile/avatar", { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { profile: UserProfile };
      setProfile(data.profile);
      emitProfileUpdated(data.profile);
      toast.success(t("profile.toasts.avatarRemoved"));
    } catch (err) {
      toast.error(t("profile.toasts.avatarRemoveFailed"), err instanceof Error ? err.message : undefined);
    }
  }

  const has = (perm: string) => profile.permissions.includes(perm);
  const granted = profile.permissions.filter((p) => PERMISSION_KEYS[p]);
  const denied = Object.keys(PERMISSION_KEYS).filter((p) => !has(p));

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 grid gap-8">
      <header className="grid gap-4 sm:grid-cols-[auto_1fr] sm:items-center sm:gap-6">
        <div className="grid place-items-center">
          <div className="relative">
            {avatarUrl ? (
              <span className="relative block h-28 w-28 shrink-0 overflow-hidden rounded-full bg-paper-deep ring-1 ring-ink/10">
                <img
                  src={avatarUrl}
                  alt=""
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    display: "block",
                  }}
                />
              </span>
            ) : (
              <span className="grid h-28 w-28 place-items-center rounded-full bg-ink text-paper text-3xl font-semibold ring-1 ring-ink/10">
                <span className="serif">{initial}</span>
              </span>
            )}
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void uploadAvatar(f);
              }}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title={t("profile.avatar.change")}
              className="absolute -bottom-1 -right-1 grid h-9 w-9 place-items-center rounded-full border border-ink/10 bg-white text-ink/65 shadow-md hover:border-gold hover:text-ink focus-ring"
            >
              <CameraIcon />
            </button>
          </div>
          <div className="mt-2 text-center text-[11px] text-ink/50">
            {uploading ? t("profile.avatar.uploading") : t("profile.avatar.limits")}
          </div>
          {profile.has_avatar ? (
            <button
              onClick={removeAvatar}
              className="mt-1 text-[11px] text-rust underline-offset-2 hover:underline"
            >
              {t("profile.avatar.remove")}
            </button>
          ) : null}
        </div>
        <div className="min-w-0">
          <p className="mono text-[11px] uppercase tracking-[0.18em] text-ink/45">
            {t("profile.kicker")} · {profile.anonymous ? t("profile.kickerAnonymous") : t("profile.kickerSignedIn")}
          </p>
          <h1 className="serif mt-1 text-3xl font-bold tracking-tight balanced">
            {profile.display_name}
          </h1>
          {profile.email ? (
            <p className="mt-1 truncate text-sm text-ink/60">{profile.email}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {profile.roles.map((r) => (
              <Badge key={r} variant={ROLE_TONE[r] ?? "paper"}>{r}</Badge>
            ))}
            {profile.global_case_scope ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-gold/40 bg-gold-soft/40 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.14em] text-ink">
                {t("profile.globalScope")}
                <InfoTip side="right" content={t("profile.globalScopeTip")} />
              </span>
            ) : null}
          </div>
          <p className="mt-3 max-w-prose text-sm text-ink/65 leading-relaxed pretty">
            {profile.bio || (
              <span className="text-ink/40">{t("profile.bioPlaceholder")}</span>
            )}
          </p>
        </div>
      </header>

      {/* ---------------- Identity & display ---------------- */}
      <section className="surface p-5 grid gap-4">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-[11px] uppercase tracking-[0.16em] text-ink/45">
            {t("profile.display.heading")}
          </h2>
          <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-ink/45">
            {t("profile.display.source")}
            <InfoTip
              side="left"
              content={
                <>
                  {t("profile.display.sourceTipPrefix")}{" "}
                  <strong className="text-ink">{t("profile.display.sourceTipBold")}</strong>
                  {t("profile.display.sourceTipSuffix")}
                </>
              }
            />
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("profile.display.fieldDisplayName")}>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={120}
              placeholder={profile.name ?? profile.email ?? profile.sub}
              className="w-full rounded-lg border border-ink/12 bg-white px-3 py-2 text-sm focus:border-gold focus:outline-none focus-ring"
            />
          </Field>
          <Field label={t("profile.display.fieldSub")} hint={t("profile.display.fieldSubHint")}>
            <code className="mono block rounded-md border border-ink/10 bg-paper-deep/50 px-3 py-2 text-xs text-ink/75">
              {profile.sub}
            </code>
          </Field>
        </div>
        <Field label={t("profile.display.fieldBio")} hint={t("profile.display.fieldBioHint")}>
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={1000}
            rows={3}
            placeholder={t("profile.display.bioInputPlaceholder")}
            className="w-full rounded-lg border border-ink/12 bg-white px-3 py-2 text-sm focus:border-gold focus:outline-none focus-ring"
          />
        </Field>
        <div className="flex items-center justify-end gap-2">
          {dirty ? (
            <button
              onClick={() => {
                setDisplayName(profile.display_name);
                setBio(profile.bio ?? "");
              }}
              className="text-xs text-ink/55 underline-offset-2 hover:text-ink hover:underline"
            >
              {t("profile.display.discard")}
            </button>
          ) : null}
          <Button onClick={saveProfile} disabled={!dirty || savingProfile}>
            {savingProfile ? t("profile.display.saving") : t("profile.display.save")}
          </Button>
        </div>
      </section>

      {/* ---------------- Permissions ---------------- */}
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="surface p-5">
          <h2 className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-ink/45">
            {t("profile.permissions.canDo")}
            <InfoTip
              side="right"
              content={
                <>
                  {t("profile.permissions.canDoTipPrefix")}{" "}
                  <strong className="text-ink">{t("profile.permissions.canDoTipBold")}</strong>
                  {t("profile.permissions.canDoTipSuffix")}
                </>
              }
            />
          </h2>
          <ul className="mt-3 grid gap-2">
            {granted.length === 0 ? (
              <li className="rounded-lg border border-dashed border-ink/15 bg-paper-deep/40 px-3 py-3 text-xs text-ink/55">
                {t("profile.permissions.canDoEmpty")}
              </li>
            ) : (
              granted.map((p) => (
                <li
                  key={p}
                  className="flex items-start gap-2 rounded-lg border border-ink/10 bg-white px-3 py-2"
                >
                  <span aria-hidden className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-fern ring-4 ring-fern/15" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">
                      {t(`profile.permissions.matrix.${PERMISSION_KEYS[p]}.label`)}
                    </div>
                    <div className="text-[11px] text-ink/55">
                      {t(`profile.permissions.matrix.${PERMISSION_KEYS[p]}.hint`)}
                    </div>
                    <code className="mono mt-1 block text-[10px] text-ink/40">{p}</code>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="surface p-5">
          <h2 className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-ink/45">
            {t("profile.permissions.needsRole")}
            <InfoTip side="left" content={t("profile.permissions.needsRoleTip")} />
          </h2>
          <ul className="mt-3 grid gap-2">
            {denied.length === 0 ? (
              <li className="rounded-lg border border-dashed border-fern/40 bg-fern/5 px-3 py-3 text-xs text-fern">
                {t("profile.permissions.noneNeeded")}
              </li>
            ) : (
              denied.map((p) => (
                <li
                  key={p}
                  className="flex items-start gap-2 rounded-lg border border-ink/8 bg-paper-deep/30 px-3 py-2 opacity-80"
                >
                  <span aria-hidden className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-ink/30 ring-4 ring-ink/8" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink/65">
                      {t(`profile.permissions.matrix.${PERMISSION_KEYS[p]}.label`)}
                    </div>
                    <div className="text-[11px] text-ink/45">
                      {t(`profile.permissions.matrix.${PERMISSION_KEYS[p]}.hint`)}
                    </div>
                    <code className="mono mt-1 block text-[10px] text-ink/40">{p}</code>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      </section>

      {/* ---------------- Quick links ---------------- */}
      <section className="surface p-5">
        <h2 className="text-[11px] uppercase tracking-[0.16em] text-ink/45">
          {t("profile.links.heading")}
        </h2>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          <QuickLink href="/cases" title={t("profile.links.casesTitle")} hint={t("profile.links.casesHint")} />
          {has("audit:global") || has("audit:case") ? (
            <QuickLink href="/audit" title={t("profile.links.auditTitle")} hint={t("profile.links.auditHint")} />
          ) : null}
          {has("plan:approve") ? (
            <QuickLink href="/cases" title={t("profile.links.approveTitle")} hint={t("profile.links.approveHint")} />
          ) : null}
          <QuickLink href="/" title={t("profile.links.uploadTitle")} hint={t("profile.links.uploadHint")} />
        </ul>
      </section>

      {/* ---------------- Audit footer ---------------- */}
      <section className="text-[11px] text-ink/45 mono flex flex-wrap items-center gap-x-4 gap-y-1">
        <span>
          {t("profile.footer.sub")} <code className="text-ink/65">{profile.sub}</code>
        </span>
        {profile.created_at ? (
          <span>
            {t("profile.footer.joined")} <DateText iso={profile.created_at} variant="date" className="text-ink/55" />
          </span>
        ) : null}
        {profile.updated_at ? (
          <span>
            {t("profile.footer.updated")} <DateText iso={profile.updated_at} variant="datetime" className="text-ink/55" />
          </span>
        ) : null}
      </section>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-ink/55">
        {label}
        {hint ? <InfoTip side="right" content={hint} /> : null}
      </span>
      {children}
    </label>
  );
}

function QuickLink({
  href,
  title,
  hint,
}: {
  href: string;
  title: string;
  hint: string;
}) {
  return (
    <li>
      <Link
        href={href}
        className="block rounded-lg border border-ink/10 bg-white px-3 py-3 transition hover:border-gold/40 hover:shadow-[0_8px_20px_-14px_rgba(212,165,52,0.45)]"
      >
        <div className="flex items-center justify-between text-sm font-medium text-ink">
          {title}
          <span aria-hidden className="text-ink/40">→</span>
        </div>
        <div className="mt-0.5 text-[12px] text-ink/55">{hint}</div>
      </Link>
    </li>
  );
}

function CameraIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );
}
