/**
 * Cross-component profile sync.
 *
 * The /profile page dispatches `verda:profile-updated` after the user
 * saves their bio/display-name or changes their avatar. The header's
 * UserMenu listens for the event and refreshes its avatar tile without
 * a full page reload.
 *
 * Pass a `ProfileUpdatedDetail` to skip the fetch round-trip; pass
 * `undefined` (no detail) when you want listeners to refetch fresh data.
 */

import type { UserProfile } from "./types";

export const PROFILE_UPDATED_EVENT = "verda:profile-updated";

export type ProfileUpdatedDetail = {
  display_name: string;
  has_avatar: boolean;
  avatar_version: number;
  avatar_url: string | null;
};

export function emitProfileUpdated(profile: UserProfile): void {
  if (typeof window === "undefined") return;
  const detail: ProfileUpdatedDetail = {
    display_name: profile.display_name,
    has_avatar: profile.has_avatar,
    avatar_version: profile.avatar_version,
    avatar_url: profile.avatar_url,
  };
  window.dispatchEvent(new CustomEvent(PROFILE_UPDATED_EVENT, { detail }));
}
