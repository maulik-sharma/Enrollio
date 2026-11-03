import { AppShell } from "@/components/app-shell";
import { LeadDetailView } from "@/components/leads/lead-detail-view";

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell>
      <LeadDetailView leadId={id} />
    </AppShell>
  );
}
