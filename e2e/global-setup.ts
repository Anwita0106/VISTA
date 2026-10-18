import { execSync } from "node:child_process";

export default function globalSetup() {
  const db = process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://vista:vista_dev_pw@localhost:5432/vista_e2e";
  // fresh, reproducible demo data for every E2E run
  execSync("python3 -m app.seed --reset", { cwd: "../backend", env: { ...process.env, DATABASE_URL: db }, stdio: "inherit" });
}
