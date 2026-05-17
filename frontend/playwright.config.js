import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.FRONTEND_BASE_URL || "http://localhost:3000";
const browserChannel = process.env.PLAYWRIGHT_BROWSER_CHANNEL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  reporter: [
    ["list"],
    ["junit", { outputFile: "../ci-cd/reports/e2e/playwright-junit.xml" }],
  ],
  outputDir: "../ci-cd/reports/e2e/playwright-artifacts",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    ...(browserChannel ? { channel: browserChannel } : {}),
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
