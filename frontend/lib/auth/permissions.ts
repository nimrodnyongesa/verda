/**
 * Frontend permission constants — kept in sync with
 * backend/wakili/auth/permissions.py.
 *
 * Importers should depend on this module rather than hard-coding strings.
 * If a permission name changes in the backend, this file is the only line
 * the frontend needs to follow.
 */

export const Permissions = {
  CasesRead: "cases:read",
  CasesCreate: "cases:create",
  CasesWrite: "cases:write",
  CasesDelete: "cases:delete",
  CasesShare: "cases:share",
  PlanApprove: "plan:approve",
  GenerationRun: "generation:run",
  ExportsBasic: "exports:basic",
  ExportsEncrypted: "exports:encrypted",
  AuditCase: "audit:case",
  AuditGlobal: "audit:global",
  UsersRead: "users:read",
  UsersManage: "users:manage",
} as const;

export type Permission = (typeof Permissions)[keyof typeof Permissions];

export type WhoamiPermissions = {
  sub: string;
  email: string | null;
  name: string | null;
  roles: string[];
  permissions: Permission[];
  global_case_scope: boolean;
  anonymous: boolean;
};

export type RoleMatrixEntry = {
  role: string;
  permissions: Permission[];
  global_case_scope: boolean;
};

export type PermissionsPayload = WhoamiPermissions & {
  role_matrix: RoleMatrixEntry[];
};

export function hasPermission(
  payload: WhoamiPermissions | null | undefined,
  ...needed: Permission[]
): boolean {
  if (!payload) return false;
  if (!needed.length) return true;
  const granted = new Set(payload.permissions);
  return needed.every((p) => granted.has(p));
}

export function hasAnyPermission(
  payload: WhoamiPermissions | null | undefined,
  ...alternatives: Permission[]
): boolean {
  if (!payload) return false;
  if (!alternatives.length) return true;
  const granted = new Set(payload.permissions);
  return alternatives.some((p) => granted.has(p));
}
