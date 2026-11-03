import { AppShell } from "@/components/app-shell";
import { LeadList } from "@/components/leads/lead-list";
import { RequirePermission } from "@/components/require-permission";

export default function LeadsPage() {
  return (
    <AppShell>
      <RequirePermission permission="leads.view_all">
        <LeadList scope="all" />
      </RequirePermission>
    </AppShell>
  );
}
