import { permanentRedirect } from "next/navigation";

const VALID = new Set([
  "plan",
  "generation",
  "timeline",
  "petition",
  "precedents",
  "procedure",
  "audit",
  "export",
]);

export default async function LegacyPanelRedirect({
  params,
}: {
  params: Promise<{ id: string; panel: string }>;
}) {
  const { id, panel } = await params;
  if (VALID.has(panel)) {
    permanentRedirect(`/cases/${id}?view=${panel}`);
  }
  permanentRedirect(`/cases/${id}`);
}
