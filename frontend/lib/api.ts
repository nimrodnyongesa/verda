import type {
  AuditEntry,
  CaseDetail,
  CaseFolder,
  CaseSummary,
  EvidenceCodex,
  GenerationEvent,
  GenerationRun,
  Plan,
  PrecedentLinker,
  ProceduralEngine,
  UserProfile,
} from "./types";

const SERVER_BASE =
  process.env.WAKILI_INTERNAL_API_BASE ?? "http://127.0.0.1:8765";

function isServer(): boolean {
  return typeof window === "undefined";
}

function joinUrl(path: string): string {
  if (!isServer()) return path;
  return SERVER_BASE.replace(/\/$/, "") + path;
}

// Server-side: fetch the access token from the cookie session and forward as
// Bearer. Client-side: rely on the same-origin /api proxy + cookie session
// (route handlers in app/api/auth/* + middleware add Authorization on demand).
async function authHeaders(): Promise<Record<string, string>> {
  if (!isServer()) return {};
  // Lazy import: keeps `next/headers` out of client bundles.
  const { getAccessToken } = await import("./auth/session");
  try {
    const token = await getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { cache?: RequestCache } = {}
): Promise<T> {
  const url = joinUrl(path);
  const auth = await authHeaders();
  const res = await fetch(url, {
    ...init,
    cache: options.cache ?? "no-store",
    headers: {
      "Content-Type": "application/json",
      ...auth,
      ...(init.headers ?? {}),
    },
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
  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ ok: boolean; llm: { configured: boolean; model: string | null } }>("/api/health"),
  whoami: () => request<{ sub: string; email: string | null; name: string | null; roles: string[]; anonymous: boolean }>("/api/auth/whoami"),
  listCases: (params?: {
    page?: number;
    per_page?: number;
    q?: string;
    folder_id?: number | null;
    root?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.per_page) qs.set("per_page", String(params.per_page));
    if (params?.q && params.q.trim()) qs.set("q", params.q.trim());
    if (params?.folder_id != null) qs.set("folder_id", String(params.folder_id));
    if (params?.root) qs.set("root", "true");
    const tail = qs.toString();
    return request<{
      cases: CaseSummary[];
      page?: number;
      per_page?: number;
      total?: number;
      total_pages?: number;
    }>(`/api/cases${tail ? `?${tail}` : ""}`);
  },
  deleteCase: (id: number) =>
    request<{ ok: boolean; case_id: number }>(`/api/cases/${id}`, {
      method: "DELETE",
    }),
  patchCase: (id: number, payload: { title?: string; description?: string }) =>
    request<{ case: CaseDetail }>(`/api/cases/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getCase: (id: number) => request<{ case: CaseDetail }>(`/api/cases/${id}`),
  createCase: (payload: Record<string, unknown>) =>
    request<{ case: CaseDetail }>("/api/cases", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadFiles: async (caseId: number, files: File[]) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f, f.name);
    const auth = await authHeaders();
    const res = await fetch(joinUrl(`/api/cases/${caseId}/files`), {
      method: "POST",
      body: fd,
      headers: { ...auth },
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return (await res.json()) as { case: CaseDetail };
  },
  refreshPlan: (caseId: number) =>
    request<{ plan: Plan }>(`/api/cases/${caseId}/plan`, { method: "POST" }),
  approvePlan: (caseId: number) =>
    request<{ plan: Plan }>(`/api/cases/${caseId}/plan/approve`, { method: "POST" }),
  generate: (caseId: number) =>
    request<{ run_id: number; case_id: number; mode: string; bundle_path: string; duration_seconds: number; summary: Record<string, unknown> }>(
      `/api/cases/${caseId}/generate`,
      { method: "POST" }
    ),
  latestRun: (caseId: number) =>
    request<{ run: GenerationRun; events: GenerationEvent[] }>(
      `/api/cases/${caseId}/runs/latest`
    ),
  timeline: (caseId: number) => request<EvidenceCodex>(`/api/cases/${caseId}/timeline`),
  precedents: (caseId: number) => request<PrecedentLinker>(`/api/cases/${caseId}/precedents`),
  procedure: (caseId: number) => request<ProceduralEngine>(`/api/cases/${caseId}/procedure`),
  petition: async (caseId: number): Promise<string> => {
    const auth = await authHeaders();
    const res = await fetch(joinUrl(`/api/cases/${caseId}/petition`), {
      cache: "no-store",
      headers: { ...auth },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  audit: (caseId?: number) =>
    request<{ entries: AuditEntry[] }>(
      caseId ? `/api/audit?case_id=${caseId}` : "/api/audit"
    ),
  // Folders -----------------------------------------------------------------
  listFolders: () => request<{ folders: CaseFolder[] }>("/api/folders"),
  createFolder: (payload: { name: string; parent_id?: number | null }) =>
    request<{ folder: CaseFolder }>("/api/folders", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  renameFolder: (id: number, name: string) =>
    request<{ folder: CaseFolder }>(`/api/folders/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  moveFolder: (id: number, parent_id: number | null) =>
    request<{ folder: CaseFolder }>(`/api/folders/${id}/move`, {
      method: "POST",
      body: JSON.stringify({ parent_id }),
    }),
  deleteFolder: (id: number) =>
    request<{ ok: boolean; folder_id: number }>(`/api/folders/${id}`, {
      method: "DELETE",
    }),
  moveCase: (caseId: number, folder_id: number | null) =>
    request<{ case_id: number; folder_id: number | null }>(
      `/api/cases/${caseId}/move`,
      {
        method: "POST",
        body: JSON.stringify({ folder_id }),
      }
    ),
  // Profile -----------------------------------------------------------------
  myProfile: () => request<{ profile: UserProfile }>("/api/me/profile"),
  patchProfile: (payload: { display_name?: string | null; bio?: string | null }) =>
    request<{ profile: UserProfile }>("/api/me/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteAvatar: () =>
    request<{ profile: UserProfile }>("/api/me/profile/avatar", {
      method: "DELETE",
    }),
};
