import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_DEMO_PASSWORD ?? "dev-only-password";

type RoleCase = {
  role: string;
  email: string;
  visible: string[];
  hidden: string[];
};

const ROLES: RoleCase[] = [
  {
    role: "system admin",
    email: "admin@enrollio.dev",
    visible: ["Users", "Roles", "Knowledge base", "Integrations", "Audit log"],
    hidden: ["My leads", "Leads", "Manager dashboard"],
  },
  {
    role: "admission manager",
    email: "manager@enrollio.dev",
    visible: [
      "Manager dashboard",
      "Leads",
      "Assignment",
      "Campaigns",
      "Lead scoring",
      "Follow-up policies",
    ],
    hidden: ["Users", "My leads"],
  },
  {
    role: "admission counsellor",
    email: "counsellor@enrollio.dev",
    visible: [
      "My leads",
      "Appointments",
      "Recordings",
      "MOM review",
      "Assessments",
      "Messages",
    ],
    hidden: ["Users", "Leads", "Manager dashboard"],
  },
];

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

for (const roleCase of ROLES) {
  test(`${roleCase.role} sees only their menu and can log out`, async ({ page }) => {
    await signIn(page, roleCase.email, PASSWORD);

    await expect(
      page.getByRole("heading", { name: /^Welcome, / }),
    ).toBeVisible();

    const navigation = page.getByRole("navigation", { name: "Main navigation" });
    for (const label of roleCase.visible) {
      await expect(
        navigation.getByRole("link", { name: label, exact: true }),
      ).toBeVisible();
    }
    for (const label of roleCase.hidden) {
      await expect(
        navigation.getByRole("link", { name: label, exact: true }),
      ).toHaveCount(0);
    }

    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);

    // The refresh cookie is gone, so a reload cannot restore the session.
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
  });
}

test("invalid credentials show a generic error", async ({ page }) => {
  await signIn(page, "admin@enrollio.dev", "definitely-wrong-password");

  await expect(page.getByText("Invalid email or password")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
