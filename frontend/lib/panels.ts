// Server-safe panel registry. Imported by both server pages and client components.
//
// `label` is now a *catalog key* (`workspace.panels.overview`, etc.) instead
// of a hard-coded English string — call sites resolve it through `t()` so the
// sidebar speaks the user's language. The `key` field is the route token and
// stays in English so deep links remain stable across locales.
export type PanelKey =
  | "overview"
  | "plan"
  | "generation"
  | "timeline"
  | "petition"
  | "precedents"
  | "procedure"
  | "audit"
  | "export";

export const PANELS: { key: PanelKey; labelKey: string; hotkey: string }[] = [
  { key: "overview",   labelKey: "workspace.panels.overview",   hotkey: "1" },
  { key: "plan",       labelKey: "workspace.panels.plan",       hotkey: "2" },
  { key: "generation", labelKey: "workspace.panels.generation", hotkey: "3" },
  { key: "timeline",   labelKey: "workspace.panels.timeline",   hotkey: "4" },
  { key: "petition",   labelKey: "workspace.panels.petition",   hotkey: "5" },
  { key: "precedents", labelKey: "workspace.panels.precedents", hotkey: "6" },
  { key: "procedure",  labelKey: "workspace.panels.procedure",  hotkey: "7" },
  { key: "audit",      labelKey: "workspace.panels.audit",      hotkey: "8" },
  { key: "export",     labelKey: "workspace.panels.export",     hotkey: "9" },
];

export function getActivePanel(view: string | null): PanelKey {
  if (view && PANELS.some((p) => p.key === view)) return view as PanelKey;
  return "overview";
}
