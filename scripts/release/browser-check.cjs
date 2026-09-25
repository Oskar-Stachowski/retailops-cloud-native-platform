const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const frontendRequire = createRequire(path.resolve(__dirname, "../../frontend/package.json"));
const { chromium, expect } = frontendRequire("@playwright/test");

(async () => {
  const [baseURL, expectedFile, reportDir] = process.argv.slice(2);
  if (new URL(baseURL).hostname !== "127.0.0.1") throw new Error("Loopback drill URL required");
  const expected = JSON.parse(fs.readFileSync(expectedFile, "utf8"));
  const channel = process.env.PLAYWRIGHT_BROWSER_CHANNEL;
  const browser = await chromium.launch(channel ? { channel } : {});
  const context = await browser.newContext();
  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();
  try {
    await page.goto(baseURL);
    await expect(page.getByRole("heading", { name: "RetailOps executive dashboard" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Backend data unavailable" })).toHaveCount(0);
    const products = page.getByLabel("Business KPI metrics").getByRole("article")
      .filter({ has: page.getByText("Products", { exact: true }) });
    await expect(products.locator("strong")).toHaveText(String(expected.snapshot.tables.products.rows));
    for (const entity of expected.entities) {
      await page.goto(`${baseURL}/products/${entity.product_id}`);
      await expect(page.getByLabel("Product 360 summary")).toBeVisible();
      const heading = entity.resource === "alerts" ? "Alerts" : "Recommendations";
      const section = page.locator("section.table-card").filter({ has: page.getByRole("heading", { name: heading, exact: true }) });
      await expect(section.getByRole("cell", { name: entity.status, exact: true }).first()).toBeVisible();
      await page.reload();
      await expect(section.getByRole("cell", { name: entity.status, exact: true }).first()).toBeVisible();
    }
    await context.tracing.stop();
    console.log(JSON.stringify({ dashboard: "passed", product360_decisions: 3, reload: "passed" }));
  } catch (error) {
    fs.mkdirSync(reportDir, { recursive: true });
    await page.screenshot({ path: path.join(reportDir, "failure.png"), fullPage: true });
    await context.tracing.stop({ path: path.join(reportDir, "trace.zip") });
    throw error;
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
