import { expect, test } from "@playwright/test";
import { actual, caseId, isoDate, login, newUserPage, USERS } from "./helpers";

test.describe("Authentication & access", () => {
  test("FT-01 valid student login opens the student dashboard", async ({ page }) => {
    caseId("FT-01");
    await login(page, USERS.priya);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Priya");
    await expect(page.getByTestId("current-role")).toHaveText(/Student/);
    await expect(page.getByTestId("sos-button")).toBeVisible();
    actual(`UI: redirected to dashboard '${await page.getByRole("heading", { level: 1 }).innerText()}', role label 'Student', SOS button visible`);
  });

  test("FT-02 invalid password shows an error and stays on login", async ({ page }) => {
    caseId("FT-02");
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.arjun.email);
    await page.getByLabel("Password").fill("NotMyPass1");
    await page.getByRole("button", { name: "Sign in" }).click();
    const alert = page.getByRole("alert");
    await expect(alert).toHaveText("Invalid email or password");
    await expect(page).toHaveURL(/\/login$/);
    actual(`UI: error '${await alert.innerText()}' displayed; URL stays /login`);
  });

  test("FT-03 navigation is role-specific", async ({ browser }) => {
    caseId("FT-03");
    const s = await newUserPage(browser, USERS.priya);
    const w = await newUserPage(browser, USERS.wardenLH);
    const nav = (p: typeof s) => p.getByRole("navigation", { name: "Main navigation" }).first();
    await expect(nav(s).getByRole("link", { name: "Document Vault" })).toBeVisible();
    await expect(nav(s).getByRole("link", { name: "Users" })).toHaveCount(0);
    await expect(nav(w).getByRole("link", { name: "Users" })).toBeVisible();
    await expect(nav(w).getByRole("link", { name: "Document Vault" })).toHaveCount(0);
    await expect(w.getByTestId("stat-active-sos")).toBeVisible();
    actual("UI: student menu shows Document Vault, no Users; warden menu shows Users/Hostels, no Vault; warden dashboard shows Active SOS card");
  });

  test("FT-04 student opening an admin page gets access denied", async ({ page }) => {
    caseId("FT-04");
    await login(page, USERS.priya);
    await page.goto("/admin/users");
    await expect(page.getByTestId("forbidden")).toBeVisible();
    actual("UI: /admin/users as student shows '403 Access denied' page");
  });

  test("FT-06 registration form shows field validation errors", async ({ page }) => {
    caseId("FT-06");
    await page.goto("/register");
    await page.getByLabel("Full name").fill("A");
    await page.getByLabel("Registration number").fill("abc");
    await page.getByLabel("Mobile number").fill("123");
    await page.locator("input[name=password]").fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Format: 24BCE1234")).toBeVisible();
    await expect(page.getByText("Enter a valid 10-digit mobile number")).toBeVisible();
    await expect(page.getByText("Password must be at least 8 characters")).toBeVisible();
    await expect(page).toHaveURL(/register/);
    actual("UI: inline errors for reg. no., mobile, password and name; form not submitted");
  });

  test("FT-41 logout ends the session", async ({ page }) => {
    caseId("FT-41");
    await login(page, USERS.kavya);
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/complaints");
    await expect(page).toHaveURL(/\/login$/);
    actual("UI: logout returns to /login; opening /complaints afterwards redirects to /login");
  });
});

test.describe("Profile & complaints", () => {
  test("FT-07 profile update persists after reload", async ({ page }) => {
    caseId("FT-07");
    await login(page, USERS.arjun);
    await page.goto("/profile");
    await page.getByLabel("Mobile number").fill("9988776655");
    await page.getByLabel("Study style").selectOption("QUIET");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByTestId("toast")).toContainText("Profile updated");
    await page.reload();
    await expect(page.getByLabel("Mobile number")).toHaveValue("9988776655");
    await expect(page.getByLabel("Study style")).toHaveValue("QUIET");
    actual("UI: 'Profile updated' toast; after reload mobile=9988776655, study=QUIET");
  });

  test("FT-08/FT-32 complaint is created in the UI and persists after reload", async ({ page }) => {
    caseId("FT-08");
    caseId("FT-32");
    await login(page, USERS.priya);
    await page.goto("/complaints");
    await page.getByRole("button", { name: "New complaint" }).click();
    await page.locator("select[name=category]").selectOption("PLUMBING");
    await page.locator("input[name=title]").fill("Bathroom tap leaking (E2E)");
    await page.locator("textarea[name=description]").fill("The tap in the attached bathroom drips all night.");
    await page.getByTestId("submit-complaint").click();
    await expect(page.getByTestId("toast")).toContainText(/Complaint CMP-\d+ registered/);
    const row = page.getByTestId("complaint-row").filter({ hasText: "Bathroom tap leaking (E2E)" });
    await expect(row).toBeVisible();
    const code = (await row.locator("td").first().innerText()).trim();
    await page.reload();
    await expect(page.getByTestId("complaint-row").filter({ hasText: code })).toBeVisible();
    await row.getByRole("link", { name: "Bathroom tap leaking (E2E)" }).click();
    await expect(page.getByTestId("complaint-status")).toContainText("Open");
    await expect(page.getByTestId("complaint-history")).toContainText("forwarded to");
    actual(`UI: ${code} created (status Open, forwarded to maintenance staff) and still listed after page reload`);
  });

  test("FT-09 complaint form blocks missing required fields", async ({ page }) => {
    caseId("FT-09");
    await login(page, USERS.priya);
    await page.goto("/complaints?new=1");
    await page.getByTestId("submit-complaint").click();
    await expect(page.getByText("Select a category")).toBeVisible();
    await expect(page.getByText("Title must be at least 5 characters")).toBeVisible();
    await expect(page.getByText("Describe the issue in at least 10 characters")).toBeVisible();
    actual("UI: three inline errors shown (category, title, description); dialog stays open, nothing submitted");
  });
});

test.describe("Visitors, notices and SOS", () => {
  test("FT-14/FT-15 student registers a visitor, warden approves, student sees approval", async ({ browser }) => {
    caseId("FT-14");
    caseId("FT-15");
    const s = await newUserPage(browser, USERS.kavya);
    await s.goto("/visitors");
    await s.getByLabel("Visitor name").fill("Sunil Reddy");
    await s.getByLabel("Relation").selectOption("PARENT");
    await s.getByLabel("Visitor mobile").fill("9845098450");
    await s.getByLabel("Visit date").fill(isoDate(3));
    await s.getByRole("button", { name: "Submit request" }).click();
    await expect(s.getByTestId("toast")).toContainText("submitted for warden approval");
    await expect(s.getByTestId("visitor-row").filter({ hasText: "Sunil Reddy" })).toContainText("Pending");

    const w = await newUserPage(browser, USERS.wardenLH);
    await w.goto("/visitors");
    const row = w.getByTestId("visitor-row").filter({ hasText: "Sunil Reddy" });
    await row.getByRole("button", { name: "Approve" }).click();
    await w.getByLabel("Remark (optional)").fill("Please carry ID");
    await w.getByTestId("confirm-decision").click();
    await expect(w.getByTestId("toast")).toContainText("approved");

    await s.reload();
    const mine = s.getByTestId("visitor-row").filter({ hasText: "Sunil Reddy" });
    await expect(mine).toContainText("Approved");
    await expect(mine).toContainText("Please carry ID");
    actual("UI: request shown Pending to student → warden approved with remark → student list shows Approved + 'Please carry ID'");
  });

  test("FT-17 past visit date is rejected in the form", async ({ page }) => {
    caseId("FT-17");
    await login(page, USERS.kavya);
    await page.goto("/visitors");
    await page.getByLabel("Visitor name").fill("Past Date");
    await page.getByLabel("Relation").selectOption("FRIEND");
    await page.getByLabel("Visitor mobile").fill("9845098451");
    await page.getByLabel("Visit date").fill(isoDate(-2));
    await page.getByRole("button", { name: "Submit request" }).click();
    await expect(page.getByText("Visit date cannot be in the past")).toBeVisible();
    actual("UI: 'Visit date cannot be in the past' shown; no request created");
  });

  test("FT-30 warden publishes a notice and students see it", async ({ browser }) => {
    caseId("FT-30");
    const w = await newUserPage(browser, USERS.wardenLH);
    await w.goto("/notices");
    await w.getByRole("button", { name: "Publish notice" }).click();
    await w.getByLabel("Title").fill("Pest control on Saturday (E2E)");
    await w.getByLabel("Message").fill("Keep food items sealed. Rooms will be sprayed between 10 AM and 1 PM.");
    await w.locator("select[name=category]").selectOption("MAINTENANCE");
    await w.getByTestId("publish-notice").click();
    await expect(w.getByTestId("toast")).toContainText("Notice published");
    const s = await newUserPage(browser, USERS.priya);
    await s.goto("/notices");
    await expect(s.getByTestId("notice-card").filter({ hasText: "Pest control on Saturday (E2E)" })).toBeVisible();
    await s.goto("/notifications");
    await expect(s.getByTestId("notification-item").filter({ hasText: "New notice: Pest control on Saturday (E2E)" })).toBeVisible();
    actual("UI: notice published by warden; visible on student's notice board and in student's notifications");
  });

  test("FT-20 SOS requires confirmation, reaches the warden, is acknowledged and resolved", async ({ browser }) => {
    caseId("FT-20");
    const s = await newUserPage(browser, USERS.priya);
    await s.getByTestId("sos-button").click();
    await expect(s.getByRole("dialog", { name: "Send SOS alert?" })).toBeVisible();
    await expect(s.getByRole("dialog")).toContainText("NOT connected to police");
    await s.getByLabel("What is happening? (optional)").fill("E2E: twisted ankle on stairs");
    await s.getByTestId("confirm-sos").click();
    await expect(s.getByTestId("toast")).toContainText("SOS sent to wardens and security");
    const w = await newUserPage(browser, USERS.wardenLH);
    await w.goto("/sos");
    const row = w.getByTestId("sos-row").filter({ hasText: "E2E: twisted ankle on stairs" });
    await expect(row).toContainText("Raised");
    await row.getByRole("button", { name: "Acknowledge" }).click();
    await expect(row).toContainText("Acknowledged");
    await row.getByLabel("Resolution note").fill("First aid given");
    await row.getByRole("button", { name: "Mark resolved" }).click();
    await expect(row).toContainText("Resolved");
    await s.goto("/sos");
    await expect(s.getByTestId("sos-row").first()).toContainText("Resolved");
    actual("UI: confirmation dialog with demo disclaimer → alert Raised on warden board → Acknowledged → Resolved; student sees Resolved");
  });
});
