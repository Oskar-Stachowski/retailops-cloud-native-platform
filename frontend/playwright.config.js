import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.FRONTEND_BASE_URL || "http://localhost:3000";
const browserChannel = process.env.PLAYWRIGHT_BROWSER_CHANNEL;

export default defineConfig({
  testDir: "./e2e",
  // Workflow tests mutate a disposable seeded database. Do not retry or race them.
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
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
      testIgnore: ["**/frontend-api-evidence.spec.js", "**/intelligence-forecasts.spec.js", "**/intelligence-suggestions.spec.js", "**/intelligence-models.spec.js", "**/intelligence-native-models.spec.js", "**/intelligence-native-forecast.spec.js"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "evidence-chromium",
      testMatch: "**/frontend-api-evidence.spec.js",
      timeout: 180_000,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "native-intelligence-chromium",
      testMatch: "**/intelligence-native-models.spec.js",
      timeout: 180_000,
      use: { ...devices["Desktop Chrome"], trace: "off", screenshot: "off" },
    },
    {
      name: "native-forecast-chromium",
      testMatch: "**/intelligence-native-forecast.spec.js",
      timeout: 180_000,
      use: { ...devices["Desktop Chrome"], trace: "off", screenshot: "off" },
    },
    {
      name: "intelligence-chromium",
      testMatch: ["**/intelligence-forecasts.spec.js", "**/intelligence-suggestions.spec.js", "**/intelligence-models.spec.js"],
      timeout: 180_000,
      use: { ...devices["Desktop Chrome"], trace: "off", screenshot: "off" },
    },
  ],
});
