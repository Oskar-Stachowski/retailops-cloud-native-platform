import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("native model SQL/API/UI reads preserve grains, lineage, pagination and private grants", async ({ page, request }) => {
  const root = process.env.INTELLIGENCE_UI_CONTROL_DIR;
  if (!root) throw new Error("The isolated intelligence UI drill must prepare this test.");
  const secret = await fs.readFile(path.join(root, "model-credential"), "utf8");
  const expected = JSON.parse(await fs.readFile(path.join(root, "model-expected.json"), "utf8"));
  const headers = { Authorization: `Bearer ${secret}` };
  const cases = [
    ["anomaly_detected", "anomalies", "AI anomalies", "anomaly_id"],
    ["stockout_risk_scored", "stockout-risks", "AI stockout risks", "risk_id"],
  ];
  // The model panels stay mounted even if legacy dashboard loading completes later.
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/dashboard/**", async (route) => {
    await blocked;
    await route.fulfill({ status: 503, body: "legacy dashboard unavailable" });
  });
  await page.goto("/anomalies");
  const report = [];
  for (const [kind, resource, title, id] of cases) {
    const panel = page.getByRole("region", { name: title, exact: true });
    await expect(panel.getByRole("table")).toHaveCount(0);
    await panel.getByLabel("Personal model read credential").fill(secret);
    await panel.getByRole("button", { name: `Connect ${title}` }).click();
    await expect(panel.getByText("Showing 50 of 70 scoped results.")).toBeVisible();
    await expect(panel).not.toContainText("foreign-model-product");
    const response = await request.get(`/api/intelligence/v2/${resource}?limit=50&offset=0`, { headers });
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toBe("no-store");
    expect((await response.json()).items.map((item) => item.result)).toEqual(expected[kind].slice(0, 50));
    const rows = await panel.getByRole("row").allTextContents();
    expect(rows.length).toBe(51);
    for (let index = 0; index < 50; index += 1) {
      const item = expected[kind][index];
      expect(rows[index + 1]).toContain(item.product_id);
      expect(rows[index + 1]).toContain(item.status);
      expect(rows[index + 1]).toContain(kind === "anomaly_detected" ? item.selling_location_id : item.stock_location_id);
      expect(rows[index + 1]).toContain(kind === "anomaly_detected" ? `${item.observed_units} / ${item.expected_units}` : item.probability === null ? "Unavailable" : `${(item.probability * 100).toFixed(2)}%`);
    }
    await panel.getByRole("button", { name: "View model lineage" }).first().click();
    const lineage = panel.getByRole("region", { name: "Model result lineage" });
    const first = expected[kind][0];
    await expect(lineage).toContainText(first[id]);
    await expect(lineage).toContainText(first.release_id);
    await expect(lineage).toContainText(first.inference_run_id);
    await expect(lineage).toContainText((first.lineage || first).source_dataset_id);
    const literal = await request.get(`/api/intelligence/v2/${resource}/${first[id]}`, { headers });
    expect(literal.status()).toBe(200);
    expect((await literal.json()).result).toEqual(first);
    await panel.getByRole("button", { name: "Next model page" }).click();
    await expect(panel.getByText("Showing 20 of 70 scoped results.")).toBeVisible();
    await expect(panel.getByRole("button", { name: "Next model page" })).toHaveCount(0);
    for (const [query, status] of [["?product_id=foreign-model-product", 403], ["?user_id=platform-admin", 422], ["?limit=101", 422]]) {
      expect((await request.get(`/api/intelligence/v2/${resource}${query}`, { headers })).status()).toBe(status);
    }
    expect((await request.get(`/api/intelligence/v2/${resource}`)).status()).toBe(401);
    report.push({ kind, counts: [50, 20], literal_native_id: true, foreign_scope: 403 });
  }
  release();
  await page.unrouteAll({ behavior: "wait" });
  for (const [, , title] of cases) {
    await expect(page.getByRole("region", { name: title, exact: true }).getByText("Showing 20 of 70 scoped results.")).toBeVisible();
  }
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(storage).includes(secret)).toBe(false);
  await page.screenshot({ path: path.join(root, "model-lineage.png"), fullPage: true });
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("retailops:demo-user-changed", { detail: { userId: "platform-admin" } })));
  for (const [, , title] of cases) {
    const panel = page.getByRole("region", { name: title, exact: true });
    await expect(panel.getByLabel("Personal model read credential")).toHaveValue("");
    await expect(panel.getByRole("table")).toHaveCount(0);
    await panel.getByLabel("Personal model read credential").fill(secret);
    await panel.getByRole("button", { name: `Connect ${title}` }).click();
    await expect(panel.getByText("Showing 50 of 70 scoped results.")).toBeVisible();
  }
  const policy = JSON.parse(await fs.readFile(path.join(root, "model-access.json"), "utf8"));
  policy.principals[0].credential_sha256 = "0".repeat(64);
  await fs.writeFile(path.join(root, "model-access.json"), JSON.stringify(policy));
  for (const [, , title] of cases) {
    const panel = page.getByRole("region", { name: title, exact: true });
    await panel.getByRole("button", { name: `Refresh ${title}` }).click();
    await expect(panel.getByRole("alert")).toContainText("AI model access was denied");
    await expect(panel.getByRole("table")).toHaveCount(0);
  }
  await fs.writeFile(path.join(root, "model-browser-report.json"), JSON.stringify({ status: "passed", scope: "synthetic_contract_mechanics_only", model_qualification: false, results: report, credential_storage: false, live_revocation: true, late_legacy_response_preserves_models: true }));
});
