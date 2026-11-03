import { AppShell } from "@/components/app-shell";
import { ManualLeadForm } from "@/components/leads/manual-lead-form";

export default function NewLeadPage() {
  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">New lead</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Create an enquiry manually. Duplicate contacts are matched to the
            existing student.
          </p>
        </div>
        <ManualLeadForm />
      </div>
    </AppShell>
  );
}
