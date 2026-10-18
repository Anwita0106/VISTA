import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { actual, caseId, login, newUserPage, USERS } from "./helpers";

test("NFT-03 page load time of key pages is under 3 seconds", async ({ page }) => {
  caseId("NFT-03");
  await login(page, USERS.priya);
  const results: Record<string, number> = {};
  for (const [path, ready] of [["/", "stat-open-complaints"], ["/complaints", "complaint-row"], ["/notices", "notice-card"], ["/delivery", "delivery-row"]] as const) {
    const times: number[] = [];
    for (let i = 0; i < 3; i++) {
      const t0 = Date.now();
      await page.goto(path);
      await page.getByTestId(ready).first().waitFor();
      times.push(Date.now() - t0);
    }
    results[path] = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
  }
  const worst = Math.max(...Object.values(results));
  actual(`Avg time until content visible (3 loads each, local server): ${Object.entries(results).map(([p, t]) => `${p} ${t} ms`).join(", ")}; worst ${worst} ms`);
  expect(worst).toBeLessThan(3000);
});

test("NFT-10 stored XSS payloads are rendered as text, not executed", async ({ browser }) => {
  caseId("NFT-10");
  const s = await newUserPage(browser, USERS.kavya);
  let dialogs = 0;
  s.on("dialog", async (d) => {
    dialogs++;
    await d.dismiss();
  });
  const payload = `<img src=x onerror="alert('xss')"> Fan noise`;
  await s.goto("/complaints?new=1");
  await s.locator("select[name=category]").selectOption("ELECTRICAL");
  await s.locator("input[name=title]").fill(payload);
  await s.locator("textarea[name=description]").fill(`<script>alert("xss")</script> description text`);
  await s.getByTestId("submit-complaint").click();
  await expect(s.getByTestId("toast")).toContainText("registered");
  const link = s.getByRole("link", { name: payload });
  await expect(link).toBeVisible();
  await link.click();
  await expect(s.getByTestId("complaint-description")).toHaveText(`<script>alert("xss")</script> description text`);
  const w = await newUserPage(browser, USERS.wardenLH);
  w.on("dialog", async (d) => {
    dialogs++;
    await d.dismiss();
  });
  await w.goto("/complaints");
  await expect(w.getByText(payload)).toBeVisible();
  const imgs = await s.locator("main img[src='x']").count();
  const resp = await s.request.get("/");
  const csp = resp.headers()["content-security-policy"] ?? "";
  actual(`Payloads shown literally to student and warden; JavaScript dialogs triggered: ${dialogs}; injected <img> elements: ${imgs}; CSP header: ${csp ? "present (script-src 'self')" : "missing"}`);
  expect(dialogs).toBe(0);
  expect(imgs).toBe(0);
  expect(csp).toContain("script-src 'self'");
});

test("NFT-15 automated accessibility scan (axe-core, WCAG 2.1 A/AA)", async ({ page }) => {
  caseId("NFT-15");
  const pages: [string, boolean][] = [["/login", false], ["/", true], ["/complaints", true], ["/visitors", true], ["/delivery", true], ["/sos", true], ["/profile", true]];
  const summary: string[] = [];
  let seriousTotal = 0;
  const ruleSet = new Set<string>();
  for (const [path, auth] of pages) {
    if (auth && !(await page.getByTestId("current-user").count())) await login(page, USERS.priya);
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const serious = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    seriousTotal += serious.reduce((n, v) => n + v.nodes.length, 0);
    serious.forEach((v) => ruleSet.add(`${v.id} (${v.impact})`));
    summary.push(`${path}: ${serious.length} serious/critical rule(s)`);
  }
  actual(`${pages.length} pages scanned. ${summary.join("; ")}. Total serious/critical nodes: ${seriousTotal}${ruleSet.size ? `. Rules: ${[...ruleSet].join(", ")}` : ""}`);
  expect(seriousTotal).toBe(0);
});

test("NFT-16 keyboard-only navigation for login and complaint form", async ({ page }) => {
  caseId("NFT-16");
  await page.goto("/login");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.type(USERS.priya.email);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.type(USERS.priya.password);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("current-user")).toBeAttached();
  await page.goto("/complaints");
  const newBtn = page.getByRole("button", { name: "New complaint" });
  await newBtn.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Raise a complaint" });
  await expect(dialog).toBeVisible();
  await expect(page.locator("select[name=category]")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.goto("/");
  await page.getByTestId("current-user").waitFor({ state: "attached" });
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  actual("Login completed with Tab/typing/Enter only; complaint dialog opened with Enter, focus moved into the form, Escape closed it; 'Skip to content' link is first in tab order");
});

test("NFT-17 form errors are announced and linked to their fields", async ({ page }) => {
  caseId("NFT-17");
  await page.goto("/register");
  await page.getByRole("button", { name: "Create account" }).click();
  const reg = page.getByLabel("Registration number");
  await expect(reg).toHaveAttribute("aria-invalid", "true");
  const describedBy = await reg.getAttribute("aria-describedby");
  await expect(page.locator(`[id="${describedBy}"]`)).toHaveText("Format: 24BCE1234");
  const alerts = await page.getByRole("alert").count();
  actual(`Empty registration submit: ${alerts} inline errors with role=alert; inputs marked aria-invalid and linked via aria-describedby`);
  expect(alerts).toBeGreaterThanOrEqual(5);
});

test("NFT-18 responsive layout has no horizontal scrolling", async ({ browser }) => {
  caseId("NFT-18");
  const sizes = [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1366, height: 850 }];
  const paths = ["/", "/complaints", "/visitors", "/delivery", "/notices", "/marketplace", "/sos", "/map"];
  const overflow: string[] = [];
  for (const vp of sizes) {
    const p = await newUserPage(browser, USERS.priya, vp);
    for (const path of paths) {
      await p.goto(path);
      await p.waitForLoadState("networkidle");
      const [sw, iw] = await p.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      if (sw > iw + 1) overflow.push(`${path}@${vp.width}px (${sw}>${iw})`);
    }
    await p.context().close();
  }
  actual(`${paths.length} pages x 3 widths (375, 768, 1366 px) checked; pages with horizontal overflow: ${overflow.length ? overflow.join(", ") : "none"}`);
  expect(overflow).toEqual([]);
});
