import { defineConfig, devices } from "@playwright/test";

/**
 * Tier C journey runner (Phase 0 stabilization plan, part A3).
 *
 * Separate from playwright.config.ts so the default `npm run e2e`
 * selection stays fast: that config ignores this directory, and
 * this config only runs it. Journeys need the live stack and a
 * real LLM, so they run serially against one browser.
 */
export default defineConfig({
  testDir: "./e2e/journeys",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      "docker compose --project-directory .. -f ../docker-compose.yml up --build frontend",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
