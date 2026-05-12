import { redirect } from "next/navigation";
import { ProfilePageClient } from "@/components/profile-page-client";
import { api } from "@/lib/api";
import { AUTH_ENABLED } from "@/lib/auth/config";
import { getSession } from "@/lib/auth/session";
import type { UserProfile } from "@/lib/types";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  // The profile page is per-user and requires identity. In anonymous /
  // dev mode we just render the synthetic user; otherwise the user must
  // be signed in or we redirect through the existing /sign-in handler.
  if (AUTH_ENABLED) {
    const session = await getSession().catch(() => null);
    if (!session) {
      redirect("/sign-in?returnTo=/profile");
    }
  }
  let profile: UserProfile | null = null;
  try {
    const r = await api.myProfile();
    profile = r.profile;
  } catch {
    profile = null;
  }
  if (!profile) {
    const { messages, fallback } = await getMessages();
    const t = (key: string, vars?: Record<string, string | number>) =>
      format(messages, fallback, key, vars);
    const body = t("profile.backendDownBody", { makeCmd: "make stack" });
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="mono text-[11px] uppercase tracking-[0.18em] text-ink/45">
          {t("profile.kicker")}
        </p>
        <h1 className="serif mt-2 text-2xl font-bold tracking-tight">
          {t("profile.backendDownTitle")}
        </h1>
        <p className="mt-2 text-sm text-ink/60">
          {body.split(/(make stack)/).map((seg, i) =>
            seg === "make stack" ? (
              <code key={i} className="mono">{seg}</code>
            ) : (
              <span key={i}>{seg}</span>
            ),
          )}
        </p>
      </div>
    );
  }
  return <ProfilePageClient initialProfile={profile} />;
}
