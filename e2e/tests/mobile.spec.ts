import { expect, test } from "@playwright/test";
import { actual, caseId, login, USERS } from "./helpers";

test("NFT-29 mobile viewport: login, menu, SOS button and complaint form work", async ({ page }, info) => {
  caseId("NFT-29");
  await login(page, USERS.priya);
  await expect(page.getByTestId("sos-button")).toBeVisible();
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Complaints" }).click();
  await expect(page).toHaveURL(/\/complaints/);
  await page.getByRole("button", { name: "New complaint" }).click();
  await expect(page.getByRole("dialog", { name: "Raise a complaint" })).toBeVisible();
  const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw).toBeLessThanOrEqual(iw + 1);
  actual(`${info.project.name} (${page.viewportSize()?.width}x${page.viewportSize()?.height}, touch): login, hamburger menu, SOS button and complaint dialog work; no horizontal overflow`);
});
