import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.dirname(fileURLToPath(import.meta.url));
const backendRoot = path.resolve(siteRoot, "../tore-backend");
const python = process.env.PLAYWRIGHT_PYTHON || "python";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `"${python}" -m uvicorn main:app --host 127.0.0.1 --port 8001`,
      cwd: backendRoot,
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///./data/playwright.db",
        TORE_ENV: "test",
        RUN_MIGRATIONS: "0",
      },
      url: "http://127.0.0.1:8001/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      cwd: siteRoot,
      env: {
        ...process.env,
        VITE_API_BASE_URL: "http://127.0.0.1:8001",
      },
      url: "http://127.0.0.1:4173/forum",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
