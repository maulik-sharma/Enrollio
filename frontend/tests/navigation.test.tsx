import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Navigation } from "@/components/navigation";

const ADMIN_PERMISSIONS = [
  "users.manage",
  "roles.manage",
  "knowledge.manage",
  "integrations.manage",
  "audit.view",
];

const MANAGER_PERMISSIONS = [
  "leads.view_all",
  "leads.assign",
  "campaigns.manage",
  "scoring.configure",
  "followup_policy.manage",
  "dashboard.manager",
];

const COUNSELLOR_PERMISSIONS = [
  "leads.view_assigned",
  "appointments.manage_own",
  "recordings.upload_own",
  "mom.review_own",
  "assessment.create_own",
  "messages.send_own",
];

function renderedLabels(permissions: readonly string[]): string[] {
  render(<Navigation permissions={permissions} />);
  const nav = screen.getByRole("navigation", { name: "Main navigation" });
  return within(nav)
    .getAllByRole("link")
    .map((link) => link.textContent?.trim() ?? "");
}

describe("Navigation", () => {
  it("shows only administration items to a system admin", () => {
    const labels = renderedLabels(ADMIN_PERMISSIONS);

    expect(labels).toEqual([
      "Users",
      "Roles",
      "Knowledge base",
      "Integrations",
      "Audit log",
    ]);
    expect(labels).not.toContain("My leads");
    expect(labels).not.toContain("Leads");
  });

  it("shows only manager items to an admission manager", () => {
    const labels = renderedLabels(MANAGER_PERMISSIONS);

    expect(labels).toEqual([
      "Manager dashboard",
      "Leads",
      "Assignment",
      "Campaigns",
      "Lead scoring",
      "Follow-up policies",
    ]);
    expect(labels).not.toContain("Users");
    expect(labels).not.toContain("My leads");
  });

  it("shows only counsellor items to an admission counsellor", () => {
    const labels = renderedLabels(COUNSELLOR_PERMISSIONS);

    expect(labels).toEqual([
      "My leads",
      "Appointments",
      "Recordings",
      "MOM review",
      "Assessments",
      "Messages",
    ]);
    expect(labels).not.toContain("Users");
    expect(labels).not.toContain("Leads");
    expect(labels).not.toContain("Manager dashboard");
  });

  it("explains when no section is available", () => {
    render(<Navigation permissions={[]} />);

    expect(
      screen.getByText("No sections are available for this account yet."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });
});
