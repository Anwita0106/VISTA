import { expect, test } from "@playwright/test";
import { actual, caseId, login, USERS } from "./helpers";

// Cross-browser smoke test (run with ALL_BROWSERS=1 for Firefox and WebKit projects).
test("NFT-26/27/28 cross-browser smoke: login, dashboard, complaints list", async ({ page }, info) => {
  caseId(info.project.name.startsWith("firefox") ? "NFT-27" : info.project.name.startsWith("webkit") ? "NFT-28" : "NFT-26");
  await login(page, USERS.priya);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Priya");
  await page.goto("/complaints");
  await expect(page.getByTestId("complaint-row").first()).toBeVisible();
  await page.goto("/delivery");
  await expect(page.getByRole("tab", { name: "My deliveries" })).toBeVisible();
  actual(`${info.project.name}: login, dashboard, complaints and deliveries pages rendered and worked`);
});
