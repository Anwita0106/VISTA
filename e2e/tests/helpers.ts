import { type Browser, expect, type Page, test } from "@playwright/test";

export const USERS = {
  priya: { email: "priya.sharma@vista.demo", password: "Student@123", name: "Priya Sharma" },
  rahul: { email: "rahul.verma@vista.demo", password: "Student@123", name: "Rahul Verma" },
  arjun: { email: "arjun.nair@vista.demo", password: "Student@123", name: "Arjun Nair" },
  kavya: { email: "kavya.reddy@vista.demo", password: "Student@123", name: "Kavya Reddy" },
  wardenLH: { email: "warden.lh@vista.demo", password: "Warden@123", name: "Mrs. Revathi Subramanian" },
  admin: { email: "admin@vista.demo", password: "Admin@123", name: "Sanjana Krishnan" },
  security: { email: "security1@vista.demo", password: "Staff@123", name: "Joseph Security Desk" },
};

export async function login(page: Page, u: { email: string; password: string }) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("current-user")).toBeAttached();
}

export async function newUserPage(browser: Browser, u: { email: string; password: string }, viewport = { width: 1366, height: 850 }) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  await login(page, u);
  return page;
}

/** Link a Playwright test to a report case ID and record what was actually observed. */
export function caseId(id: string) {
  test.info().annotations.push({ type: "case", description: id });
}
export function actual(text: string) {
  test.info().annotations.push({ type: "actual", description: text });
}

export function isoDate(offsetDays: number) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date(Date.now() + offsetDays * 86400000));
}
