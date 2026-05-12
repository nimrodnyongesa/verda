export type CaseSummary = {
  id: number;
  title: string;
  jurisdiction: string;
  legal_track: string;
  description: string;
  status: string;
  filing_deadline_date: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  file_count?: number;
  latest_run_id?: number | null;
  folder_id?: number | null;
};

export type CaseFolder = {
  id: number;
  name: string;
  parent_id: number | null;
  owner_sub: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type UserProfile = {
  sub: string;
  email: string | null;
  name: string | null;
  display_name: string;
  bio: string;
  roles: string[];
  permissions: string[];
  global_case_scope: boolean;
  anonymous: boolean;
  has_avatar: boolean;
  avatar_version: number;
  avatar_url: string | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

export type CaseFile = {
  id: number;
  case_id: number;
  original_name: string;
  mime_type: string;
  evidence_kind: string;
  size_bytes: number;
  sha256: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type PlanModule = {
  key: string;
  name: string;
  rationale: string;
  estimated_minutes: number;
};

export type Plan = {
  case_id: number;
  legal_track_label: string;
  citation: string;
  summary: string;
  modules: PlanModule[];
  deadlines: { label: string; date: string; rationale: string }[];
  risks: string[];
  evidence_overview: {
    files_indexed: number;
    events_extracted: number;
    issue_heatmap: { name: string; score: number }[];
    gaps: { from: string; to: string; days: number; note: string }[];
  };
  approved: boolean;
  generated_by: string;
};

export type CaseDetail = CaseSummary & {
  files: CaseFile[];
  plan: Plan | null;
  latest_run: GenerationRun | null;
};

export type GenerationRun = {
  id: number;
  case_id: number;
  generator_mode: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  status: string;
  bundle_path: string | null;
  summary: Record<string, unknown>;
};

export type GenerationEvent = {
  id: number;
  run_id: number;
  sequence: number;
  actor: string;
  kind: string;
  title: string;
  detail: string;
  file_path: string | null;
  delay_ms: number;
  created_at: string;
};

export type TimelineEvent = {
  id: string;
  date: string | null;
  summary: string;
  source_file: string;
  source_file_id: number;
  source_kind: string;
  line_number: number;
  officers_in_context: { rank: string; name: string }[];
  ob_numbers_in_context: string[];
};

export type EvidenceCodex = {
  case_id: number;
  files_indexed: number;
  events_extracted: number;
  officers_named: number;
  stations_named: number;
  ob_numbers_seen: number;
  articles_invoked: string[];
  issue_heatmap: { name: string; score: number }[];
  gaps: { from: string; to: string; days: number; note: string }[];
  timeline: TimelineEvent[];
  officers: { rank: string; name: string; mentions: number; sources: string[] }[];
  stations: string[];
  ob_numbers: string[];
};

export type Precedent = {
  citation: string;
  title: string;
  court: string;
  year: number;
  url: string;
  articles_cited: string[];
  issues: string[];
  summary: string;
  binding: boolean;
  relevance_score: number;
  match_reasons: string[];
};

export type PrecedentLinker = {
  jurisdiction: string;
  case_articles: string[];
  issues_used: string[];
  results: Precedent[];
  result_count: number;
  suggested_queries: string[];
  verification_note: string;
};

export type ProceduralEngine = {
  jurisdiction: string;
  track: string;
  track_label: string;
  citation: string;
  anchor_date: string;
  today: string;
  schedule: {
    filing: string;
    purpose: string;
    rule: string;
    deadline: string;
    days_remaining: number;
    status: "pending" | "due_soon" | "overdue";
    template: string | null;
    annexures: string[];
  }[];
  next_action: { filing: string; deadline: string; days_remaining: number } | null;
  required_filings: string[];
  drafted_motions: { filing: string; template: string; content: string }[];
  state: string;
};

export type AuditEntry = {
  id: number;
  case_id: number | null;
  actor: string;
  action: string;
  resource: string;
  payload: Record<string, unknown>;
  created_at: string;
};
