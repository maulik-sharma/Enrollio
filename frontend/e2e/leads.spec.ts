import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { randomInt } from "node:crypto";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_DEMO_PASSWORD ?? "dev-only-password";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const FIXTURE = join(process.cwd(), "e2e/fixtures/leads-import.csv");

/**
 * Copy the committed 100-row fixture with unique contacts so the suite can run
 * repeatedly against a development database without becoming a fake duplicate
 * test on the second run.
 */
function uniqueFixture(): string {
  const suffix = `${Date.now().toString(36)}${randomInt(1000, 9999)}`;
  const offset = randomInt(0, 7000);
  let index = 0;
  const contents = readFileSync(FIXTURE, "utf8")
    .replaceAll("@example.com", `.${suffix}@example.com`)
    .replace(/\b900000\d{4}\b/g, () => {
      const number = `9${String(offset * 100 + index).padStart(9, "0")}`;
      index += 1;
      return number;
    });
  const directory = join(process.cwd(), "test-results");
  mkdirSync(directory, { recursive: true });
  const path = join(directory, `leads-import-${suffix}.csv`);
  writeFileSync(path, contents, "utf8");
  return path;
}

async function signIn(page: Page, email: string) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /^Welcome, / })).toBeVisible();
}

async function apiToken(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const response = await request.post(`${API_URL}/api/auth/login`, {
    data: { email, password: PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { access_token: string };
  return body.access_token;
}

test("manager imports a fixture file and sees exact counts", async ({
  page,
}) => {
  await signIn(page, "manager@enrollio.dev");

  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Leads", exact: true })
    .click();
  await page.getByRole("link", { name: "Import leads" }).click();

  await expect(
    page.getByRole("heading", { name: "Import leads" }),
  ).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(uniqueFixture());
  await page.getByLabel("Partner or source name").fill("E2E Coaching Partner");
  await page.getByRole("button", { name: "Continue to mapping" }).click();

  await expect(
    page.getByRole("heading", { name: "Map columns" }),
  ).toBeVisible();
  await expect(page.getByLabel("Map Email")).toHaveValue("email");
  await expect(page.getByLabel("Map Phone")).toHaveValue("phone");
  await expect(page.getByLabel("Map Score")).toHaveValue("score");

  await page.getByRole("button", { name: "Start import" }).click();

  await expect(
    page.getByRole("heading", { name: "Import finished" }),
  ).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("count-rows")).toHaveText("100");
  await expect(page.getByTestId("count-created")).toHaveText("85");
  await expect(page.getByTestId("count-merged")).toHaveText("0");
  await expect(page.getByTestId("count-duplicates")).toHaveText("5");
  await expect(page.getByTestId("count-rejected")).toHaveText("10");

  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download error report (CSV)" })
    .click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).not.toBeNull();
  const report = readFileSync(path as string, "utf8");
  const lines = report.trim().split("\n");
  expect(lines).toHaveLength(11);
  expect(lines[0]).toBe("row_number,reason");
  for (const reason of [
    "invalid_email",
    "invalid_phone",
    "missing_contact",
    "invalid_name",
    "invalid_score",
    "invalid_graduation_year",
  ]) {
    expect(report).toContain(reason);
  }

  await page.getByRole("link", { name: "View leads" }).click();
  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();
});

test("counsellor sees only leads assigned to them", async ({
  page,
  request,
}) => {
  const stamp = Date.now().toString(36);
  const assignedName = `AssignedA${stamp}`;
  const hiddenName = `HiddenB${stamp}`;

  const adminToken = await apiToken(request, "admin@enrollio.dev");
  const usersResponse = await request.get(`${API_URL}/api/users?limit=200`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(usersResponse.ok()).toBeTruthy();
  const users = (await usersResponse.json()) as {
    id: string;
    email: string;
  }[];
  const counsellor = users.find((user) => user.email === "counsellor@enrollio.dev");
  expect(counsellor).toBeDefined();

  const managerToken = await apiToken(request, "manager@enrollio.dev");
  const headers = {
    Authorization: `Bearer ${managerToken}`,
  };
  const assigned = await request.post(`${API_URL}/api/leads`, {
    headers,
    data: {
      first_name: assignedName,
      last_name: "Visible",
      email: `assigned.${stamp}@example.com`,
      assigned_counsellor_id: counsellor?.id,
    },
  });
  expect(assigned.ok()).toBeTruthy();

  const hidden = await request.post(`${API_URL}/api/leads`, {
    headers,
    data: {
      first_name: hiddenName,
      last_name: "Hidden",
      email: `hidden.${stamp}@example.com`,
    },
  });
  expect(hidden.ok()).toBeTruthy();

  await signIn(page, "counsellor@enrollio.dev");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "My leads", exact: true })
    .click();

  await page.getByLabel("Search").fill(stamp);
  await page.getByRole("button", { name: "Apply filters" }).click();

  await expect(page.getByText(assignedName)).toBeVisible();
  await expect(page.getByText(hiddenName)).toHaveCount(0);
});
