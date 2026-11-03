import { AppShell } from "@/components/app-shell";
import { LeadList } from "@/components/leads/lead-list";
import { RequirePermission } from "@/components/require-permission";

export default function MyLeadsPage() {
  return (
    <AppShell>
      <RequirePermission permission="leads.view_assigned">
        <LeadList scope="assigned" />
      </RequirePermission>
    </AppShell>
  );
}
