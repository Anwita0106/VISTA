import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 8001);
const DB = process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://vista:vista_dev_pw@localhost:5432/vista_e2e";
const allBrowsers = !!process.env.ALL_BROWSERS;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "../test-results/playwright-results.json" }],
    ["junit", { outputFile: "../test-results/playwright-junit.xml" }],
    ["html", { outputFolder: "../test-results/playwright-html", open: "never" }],
  ],
  globalSetup: "./global-setup.ts",
  use: {
    baseURL: `http://localhost:${PORT}`,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : undefined,
  },
  outputDir: "../test-results/playwright-artifacts",
  webServer: {
    command: `python3 -m uvicorn app.main:app --port ${PORT}`,
    cwd: "../backend",
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { DATABASE_URL: DB, ESCALATION_CHECK_SECONDS: "0", UPLOAD_DIR: "../backend/.e2e-uploads", CORS_ORIGINS: `http://localhost:${PORT}` },
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 850 } }, testIgnore: /mobile\.spec/ },
    { name: "mobile-pixel5", use: { ...devices["Pixel 5"] }, testMatch: /mobile\.spec/ },
    { name: "mobile-iphone12-chromium", use: { ...devices["iPhone 12"], browserName: "chromium", defaultBrowserType: "chromium" }, testMatch: /mobile\.spec/ },
    ...(allBrowsers
      ? [
          { name: "firefox-desktop", use: { ...devices["Desktop Firefox"] }, testMatch: /smoke\.spec/ },
          { name: "webkit-desktop", use: { ...devices["Desktop Safari"] }, testMatch: /smoke\.spec/ },
        ]
      : []),
  ],
});
