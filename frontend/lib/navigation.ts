export type NavItem = {
  slug: string;
  label: string;
  permission: string;
};

/**
 * The navigation mirrors the RBAC catalog: an item is visible only when the
 * user's flattened permissions include its requirement. Routes for most items
 * arrive with later milestones; M1.5 renders a placeholder for them.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { slug: "dashboard", label: "Manager dashboard", permission: "dashboard.manager" },
  { slug: "leads", label: "Leads", permission: "leads.view_all" },
  { slug: "assignment", label: "Assignment", permission: "leads.assign" },
  { slug: "campaigns", label: "Campaigns", permission: "campaigns.manage" },
  { slug: "scoring", label: "Lead scoring", permission: "scoring.configure" },
  {
    slug: "follow-up-policies",
    label: "Follow-up policies",
    permission: "followup_policy.manage",
  },
  { slug: "my-leads", label: "My leads", permission: "leads.view_assigned" },
  {
    slug: "appointments",
    label: "Appointments",
    permission: "appointments.manage_own",
  },
  {
    slug: "recordings",
    label: "Recordings",
    permission: "recordings.upload_own",
  },
  { slug: "mom", label: "MOM review", permission: "mom.review_own" },
  {
    slug: "assessments",
    label: "Assessments",
    permission: "assessment.create_own",
  },
  { slug: "messages", label: "Messages", permission: "messages.send_own" },
  { slug: "users", label: "Users", permission: "users.manage" },
  { slug: "roles", label: "Roles", permission: "roles.manage" },
  { slug: "knowledge", label: "Knowledge base", permission: "knowledge.manage" },
  {
    slug: "integrations",
    label: "Integrations",
    permission: "integrations.manage",
  },
  { slug: "audit", label: "Audit log", permission: "audit.view" },
];

/** Items the user may see, preserving the catalog order. */
export function visibleNavItems(
  permissions: readonly string[],
): NavItem[] {
  const granted = new Set(permissions);
  return NAV_ITEMS.filter((item) => granted.has(item.permission));
}

/** Look up an item by slug, whether or not the user may see it. */
export function navItemBySlug(slug: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => item.slug === slug);
}
