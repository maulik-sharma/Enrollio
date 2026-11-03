import { AppShell } from "@/components/app-shell";
import { ImportWizard } from "@/components/imports/import-wizard";
import { RequirePermission } from "@/components/require-permission";

export default function ImportLeadsPage() {
  return (
    <AppShell>
      <RequirePermission permission="leads.view_all">
        <ImportWizard />
      </RequirePermission>
    </AppShell>
  );
}
