import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("original v12 functionals, complete native identities and development scope reach the built panel", async ({ page, request }) => {
  const root = process.env.AI10_NATIVE_BROWSER_CONTROL;
  if (!root) throw new Error("The original native v12 acceptance must prepare this test.");
  const secret = await fs.readFile(path.join(root, "credential"), "utf8");
  const cases = JSON.parse(await fs.readFile(path.join(root, "expected.json"), "utf8"));
  const items = cases[0].items;
  expect(items.length).toBe(56);
  const originals = new Map(items.map((item) => [item.prediction_id, item]));
  const headers = { Authorization: `Bearer ${secret}` };
  const anonymous = await request.get("/api/intelligence/v2/forecasts?user_id=platform-admin");
  expect(anonymous.status()).toBe(401);
  const escalation = await request.get("/api/intelligence/v2/forecasts?user_id=platform-admin", { headers });
  expect(escalation.status()).toBe(422);
  const foreign = await request.get("/api/intelligence/v2/forecasts?product_id=foreign-product", { headers });
  expect(foreign.status()).toBe(403);
  await page.goto("/forecasts");
  const panel = page.getByRole("region", { name: "AI forecasts", exact: true });
  await expect(panel.getByRole("table")).toHaveCount(0);
  await panel.getByLabel("Personal AI read credential").fill(secret);
  await panel.getByRole("button", { name: "Connect AI forecasts" }).click();
  const seen = new Set();
  let offset = 0;
  let view;
  let pages = 0;
  do {
    const query = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (view) query.set("view_sha256", view);
    const response = await request.get(`/api/intelligence/v2/forecasts/active?${query}`, { headers });
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toBe("no-store");
    const body = await response.json();
    expect(body.pagination.total).toBe(56);
    view = body.view_sha256;
    await expect(panel.getByText(`Showing ${body.items.length} of 56 scoped results.`)).toBeVisible();
    await expect(panel.getByRole("status")).toContainText("Development acceptance only. The original model quality remains not_ready.");
    const rows = panel.getByRole("row");
    await expect(rows).toHaveCount(body.items.length + 1);
    for (let index = 0; index < body.items.length; index += 1) {
      const returned = body.items[index];
      const item = originals.get(returned.forecast.prediction_id);
      expect(item).toBeDefined();
      expect(returned.forecast).toEqual(item);
      expect(seen.has(item.prediction_id)).toBe(false);
      seen.add(item.prediction_id);
      const cells = rows.nth(index + 1).getByRole("cell");
      await expect(cells.nth(0).locator(".identifier-text")).toHaveAttribute("aria-label", item.product_id);
      await expect(cells.nth(1)).toHaveText(`${item.selling_location_id} / ${item.channel}`);
      await expect(cells.nth(3)).toHaveText(`${item.target_date} / ${item.horizon_days}`);
      await expect(cells.nth(4)).toHaveText(item.prediction.candidate.mean === null ? "Unavailable" : String(item.prediction.candidate.mean));
      await expect(cells.nth(5)).toHaveText(item.prediction.baseline.median === null ? "Unavailable" : String(item.prediction.baseline.median));
      await rows.nth(index + 1).getByRole("button", { name: "View lineage" }).click();
      const lineage = panel.getByRole("region", { name: "Forecast lineage" });
      for (const field of ["prediction_id", "release_id", "inference_run_id", "prediction_dataset_id", "source_dataset_id", "feature_set_id", "receipt_id", "runtime_pin_sha256", "image_digest"]) {
        await expect(lineage).toContainText(item[field]);
      }
      await expect(lineage).toContainText(item.prediction.metadata.recipe_id);
    }
    pages += 1;
    offset = body.pagination.next_offset;
    if (offset !== null) await panel.getByRole("button", { name: "Next AI page" }).click();
  } while (offset !== null);
  expect(seen.size).toBe(56);
  expect(pages).toBe(2);
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(storage).includes(secret)).toBe(false);
  const policy = JSON.parse(await fs.readFile(process.env.AI10_NATIVE_BROWSER_POLICY, "utf8"));
  policy.principals[0].credential_sha256 = "0".repeat(64);
  await fs.writeFile(process.env.AI10_NATIVE_BROWSER_POLICY, JSON.stringify(policy));
  await panel.getByRole("button", { name: "Refresh AI forecasts" }).click();
  await expect(panel.getByRole("alert")).toContainText("AI access was denied");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByLabel("Personal AI read credential")).toHaveValue("");
  await fs.writeFile(process.env.AI10_NATIVE_BROWSER_REPORT, JSON.stringify({ status: "passed", scope: "original_v12_native_forecasts_in_built_RetailOps_UI", rows: 56, pages, original_payloads: true, literal_native_ids: true, original_lineage_in_UI: true, development_warning_visible: true, original_quality_reclassified: false, fixture_fallback: false, credential_storage: false, live_revocation: true }));
});
