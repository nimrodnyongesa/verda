"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { confirmDanger } from "@/lib/dialog";
import {
  PROFILE_UPDATED_EVENT,
  type ProfileUpdatedDetail,
} from "@/lib/profile-events";
import { useT } from "@/lib/i18n/provider";
import { LanguagePicker } from "@/components/language-picker";

type Me =
  | { enabled: false }
  | {
      enabled: true;
      user:
        | { sub: string; email?: string; name?: string; providerId: string }
        | null;
    };

type ProfileSummary = {
  display_name: string;
  has_avatar: boolean;
  avatar_version: number;
  avatar_url: string | null;
};

export function UserMenu() {
  const t = useT();
  const [me, setMe] = useState<Me | null>(null);
  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => r.json())
      .then((j: Me) => setMe(j))
      .catch(() => setMe({ enabled: false }));
  }, []);

  // Pull the profile (display name + avatar metadata) once we know we
  // have a signed-in user. The avatar_url is keyed by avatar_version so
  // a fresh upload busts the browser cache automatically.
  const loadProfile = useCallback(async () => {
    try {
      const r = await fetch("/api/be/me/profile");
      if (!r.ok) return;
      const j = await r.json();
      if (!j?.profile) return;
      setProfile({
        display_name: j.profile.display_name,
        has_avatar: !!j.profile.has_avatar,
        avatar_version: j.profile.avatar_version ?? 0,
        avatar_url: j.profile.avatar_url ?? null,
      });
    } catch {
      /* keep previous profile */
    }
  }, []);

  useEffect(() => {
    if (!me || me.enabled === false || !me.user) return;
    let alive = true;
    void (async () => {
      await loadProfile();
      if (!alive) return;
    })();
    return () => {
      alive = false;
    };
  }, [me, loadProfile]);

  // Cross-component refresh: the /profile page dispatches
  // `verda:profile-updated` after a save / avatar upload / removal so
  // the header avatar updates without a full reload. We accept either an
  // inline detail payload (fast path — no extra fetch) or fall back to a
  // fresh GET when the event has no detail.
  useEffect(() => {
    if (!me || me.enabled === false || !me.user) return;
    const onUpdate = (e: Event) => {
      const detail = (e as CustomEvent<ProfileUpdatedDetail>).detail;
      if (detail) {
        setProfile({
          display_name: detail.display_name,
          has_avatar: detail.has_avatar,
          avatar_version: detail.avatar_version,
          avatar_url: detail.avatar_url,
        });
      } else {
        void loadProfile();
      }
    };
    window.addEventListener(PROFILE_UPDATED_EVENT, onUpdate);
    return () => window.removeEventListener(PROFILE_UPDATED_EVENT, onUpdate);
  }, [me, loadProfile]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!me || me.enabled === false) {
    return (
      <span className="inline-flex items-center gap-2 rounded-md border border-ink/12 bg-paper-deep/60 px-2.5 py-1 text-[11px] text-ink/55">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ink/30" />
        {t("header.anonymous")}
      </span>
    );
  }
  if (!me.user) {
    return (
      <a
        href="/sign-in"
        className="inline-flex items-center gap-2 rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-ink-soft focus-ring"
      >
        {t("header.signIn")}
      </a>
    );
  }

  const u = me.user;
  const display = profile?.display_name ?? u.name ?? u.email ?? u.sub;
  const initial = display.slice(0, 1).toUpperCase();
  const avatarUrl = profile?.has_avatar
    ? `/api/be/me/profile/avatar?v=${profile.avatar_version}`
    : null;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="grid h-9 w-9 place-items-center rounded-full bg-transparent p-0 text-ink/85 transition hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-gold/45"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("userMenu.openProfileMenu", { name: display })}
      >
        {avatarUrl ? (
          <span className="relative block h-8 w-8 shrink-0 overflow-hidden rounded-full bg-paper-deep">
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
          <span className="grid h-8 w-8 place-items-center rounded-full bg-ink text-paper text-[12px] font-semibold">
            <span className="serif">{initial}</span>
          </span>
        )}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-64 overflow-hidden rounded-xl border border-ink/10 bg-white shadow-2xl shadow-ink/20"
        >
          <div className="border-b border-ink/8 p-3">
            <div className="flex items-center gap-3">
              {avatarUrl ? (
                <span className="relative block h-10 w-10 shrink-0 overflow-hidden rounded-full bg-paper-deep">
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
                <span className="grid h-10 w-10 place-items-center rounded-full bg-ink text-paper text-sm font-semibold">
                  {initial}
                </span>
              )}
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{display}</div>
                {u.email ? (
                  <div className="truncate text-xs text-ink/55">{u.email}</div>
                ) : null}
                <div className="mt-1 inline-flex items-center gap-1 rounded-full border border-ink/10 bg-paper-deep/40 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-ink/50">
                  {t("userMenu.via", { provider: u.providerId })}
                </div>
              </div>
            </div>
          </div>
          <ul className="py-1 text-sm">
            <li>
              <Link
                href="/profile"
                onClick={() => setOpen(false)}
                className="block px-3 py-2 text-ink/80 hover:bg-paper-deep/60 hover:text-ink"
              >
                {t("userMenu.myProfile")}
              </Link>
            </li>
            <li>
              <Link
                href="/audit"
                onClick={() => setOpen(false)}
                className="block px-3 py-2 text-ink/80 hover:bg-paper-deep/60 hover:text-ink"
              >
                {t("userMenu.auditLog")}
              </Link>
            </li>
          </ul>
          <div className="border-t border-ink/8">
            <LanguagePicker variant="menu" />
          </div>
          <ul className="border-t border-ink/8 py-1 text-sm">
            <li>
              <button
                onClick={async (e) => {
                  e.preventDefault();
                  setOpen(false);
                  const ok = await confirmDanger({
                    title: t("userMenu.signOutTitle"),
                    body: t("userMenu.signOutBody", { provider: u.providerId }),
                    confirmLabel: t("userMenu.signOutConfirm"),
                    cancelLabel: t("userMenu.signOutCancel"),
                  });
                  if (ok) {
                    window.location.href = "/api/auth/logout?returnTo=/";
                  }
                }}
                className="block w-full text-left px-3 py-2 text-rust hover:bg-rust/8 focus-ring"
              >
                {t("userMenu.signOut")}
              </button>
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
