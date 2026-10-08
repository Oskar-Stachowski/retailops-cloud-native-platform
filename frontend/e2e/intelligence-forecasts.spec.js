import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("scoped daily forecasts, lineage, pagination, revocation and browser isolation", async ({ page, request }) => {
  const root = process.env.INTELLIGENCE_UI_CONTROL_DIR;
  if (!root) throw new Error("The isolated intelligence UI drill must prepare this test.");
  const secret = await fs.readFile(path.join(root, "credential"), "utf8");
  const expected = JSON.parse(await fs.readFile(path.join(root, "expected.json"), "utf8"));
  const panel = page.getByRole("region", { name: "AI forecasts", exact: true });
  const summaries = [];

  async function connect() {
    await panel.getByLabel("Personal AI read credential").fill(secret);
    await panel.getByRole("button", { name: "Connect AI forecasts" }).click();
    await expect(panel.getByRole("heading", { name: "Daily AI forecast results" })).toBeVisible();
  }

  await page.goto("/forecasts");
  await expect(panel.getByLabel("Personal AI read credential")).toBeVisible();
  await expect(panel.getByRole("table")).toHaveCount(0);
  const anonymous = await request.get("/api/intelligence/v2/forecasts?user_id=platform-admin");
  expect(anonymous.status()).toBe(401);
  expect(anonymous.headers()["cache-control"]).toBe("no-store");
  const foreign = await request.get("/api/intelligence/v2/forecasts?product_id=foreign-product", { headers: { Authorization: `Bearer ${secret}` } });
  expect(foreign.status()).toBe(403);
  const impersonation = await request.get("/api/intelligence/v2/forecasts?user_id=platform-admin", { headers: { Authorization: `Bearer ${secret}` } });
  expect(impersonation.status()).toBe(422);
  const headers = { Authorization: `Bearer ${secret}` };
  const firstResponse = await request.get("/api/intelligence/v2/forecasts/active?limit=50&offset=0", { headers });
  expect(firstResponse.ok()).toBeTruthy();
  const first = await firstResponse.json();
  expect(first.items.map((item) => item.forecast)).toEqual(expected.slice(0, 50));
  expect(firstResponse.headers()["cache-control"]).toBe("no-store");

  await connect();
  await expect(panel.getByText("Showing 50 of 70 scoped results.")).toBeVisible();
  await expect(panel).not.toContainText("foreign-product");
  const rows = panel.getByRole("row");
  await expect(rows).toHaveCount(51);
  const rendered = await rows.allTextContents();
  for (let index = 0; index < 50; index += 1) {
    expect(rendered[index + 1]).toContain(expected[index].product_id);
    expect(rendered[index + 1]).toContain(expected[index].target_date);
    expect(rendered[index + 1]).toContain(String(expected[index].prediction.candidate.mean));
  }
  await panel.getByRole("button", { name: "View lineage" }).first().click();
  const lineage = panel.getByRole("region", { name: "Forecast lineage" });
  await expect(lineage).toContainText(expected[0].prediction_id);
  await expect(lineage).toContainText(expected[0].inference_run_id);
  await expect(lineage).toContainText(expected[0].source_dataset_id);
  await expect(lineage).toContainText("unknown: source_watermark_unavailable");
  await page.screenshot({ path: path.join(root, "forecast-lineage.png"), fullPage: true });

  await panel.getByRole("button", { name: "Next AI page" }).click();
  await expect(panel.getByText("Showing 20 of 70 scoped results.")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Next AI page" })).toHaveCount(0);
  summaries.push("actual scoped API payloads and 50/20 UI pagination");

  // Changing the selected immutable publication invalidates the old view.
  const oldView = first.view_sha256;
  const policy = JSON.parse(await fs.readFile(path.join(root, "head.json"), "utf8"));
  const replacement = JSON.parse(await fs.readFile(path.join(root, "replacement-head.json"), "utf8"));
  await fs.writeFile(path.join(root, "head.json"), JSON.stringify(replacement));
  const changed = await request.get(`/api/intelligence/v2/forecasts/active?limit=50&offset=50&view_sha256=${oldView}`, { headers });
  expect(changed.status()).toBe(409);
  await panel.getByRole("button", { name: "First AI page" }).click();
  await expect(panel.getByText("Showing 7 of 7 scoped results.")).toBeVisible();
  await fs.writeFile(path.join(root, "head.json"), JSON.stringify(policy));
  await panel.getByLabel("Publication view").selectOption("history");
  await expect(panel.getByText("Showing 50 of 77 scoped results.")).toBeVisible();
  await expect(panel).toContainText("Historical publications");
  await panel.getByRole("button", { name: "Next AI page" }).click();
  await expect(panel).toContainText("stale");
  summaries.push("operator head replacement rejects old view; historical stale results remain explicit");

  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(storage).includes(secret)).toBe(false);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("retailops:demo-user-changed", { detail: { userId: "platform-admin" } })));
  await expect(panel.getByLabel("Personal AI read credential")).toHaveValue("");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await connect();

  await panel.getByLabel("Publication view").selectOption("active");
  await expect(panel.getByText("Showing 50 of 70 scoped results.")).toBeVisible();

  // A response already in flight must not repopulate a disconnected panel.
  let release;
  let entered;
  const blocked = new Promise((resolve) => { release = resolve; });
  const intercepted = new Promise((resolve) => { entered = resolve; });
  await page.route("**/api/intelligence/v2/forecasts/active?**", async (route) => {
    const response = await route.fetch();
    entered();
    await blocked;
    try { await route.fulfill({ response }); } catch { /* disconnect cancels this request */ }
  });
  await panel.getByRole("button", { name: "Refresh AI forecasts" }).click();
  await intercepted;
  await panel.getByRole("button", { name: "Disconnect AI forecasts" }).click();
  release();
  await page.unrouteAll({ behavior: "wait" });
  await expect(panel.getByRole("table")).toHaveCount(0);
  await connect();

  // Revocation is read on the next request by the running API, with no restart.
  const access = JSON.parse(await fs.readFile(path.join(root, "access.json"), "utf8"));
  access.principals[0].credential_sha256 = "0".repeat(64);
  await fs.writeFile(path.join(root, "access.json"), JSON.stringify(access));
  await panel.getByRole("button", { name: "Refresh AI forecasts" }).click();
  await expect(panel.getByRole("alert")).toContainText("AI access was denied");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByLabel("Personal AI read credential")).toHaveValue("");
  summaries.push("no stored credentials; demo switch and disconnect cancel reads; live revocation removes results");
  await fs.writeFile(path.join(root, "browser-report.json"), JSON.stringify({ status: "passed", anonymous: 401, foreign_scope: 403, user_id_override: 422, changed_view: 409, counts: [50, 20], expected_results: expected.length, assertions: summaries }));
});
