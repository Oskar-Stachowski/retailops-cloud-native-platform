import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test("original model publications reach the built RetailOps panels without changed payloads", async ({ page, request }) => {
  const root = process.env.AI10_NATIVE_BROWSER_CONTROL;
  if (!root) throw new Error("The qualified native acceptance must prepare this test.");
  const secret = await fs.readFile(path.join(root, "credential"), "utf8");
  const cases = JSON.parse(await fs.readFile(path.join(root, "expected.json"), "utf8"));
  const headers = { Authorization: `Bearer ${secret}` };
  await page.goto("/anomalies");
  const results = [];
  for (const { resource, title, id, kind, items } of cases) {
    expect(items.length).toBeGreaterThan(0);
    expect(items.length).toBeLessThanOrEqual(1400);
    const originals = new Map(items.map((item) => [item[id], item]));
    expect(originals.size).toBe(items.length);
    const panel = page.getByRole("region", { name: title, exact: true });
    await expect(panel.getByRole("table")).toHaveCount(0);
    await panel.getByLabel("Personal model read credential").fill(secret);
    await panel.getByRole("button", { name: `Connect ${title}` }).click();
    const seen = new Set();
    let offset = 0;
    let view;
    let pages = 0;
    do {
      const query = new URLSearchParams({ limit: "50", offset: String(offset) });
      if (view) query.set("view_sha256", view);
      const response = await request.get(`/api/intelligence/v2/${resource}?${query}`, { headers });
      expect(response.status()).toBe(200);
      expect(response.headers()["cache-control"]).toBe("no-store");
      const body = await response.json();
      expect(body.pagination.total).toBe(items.length);
      expect(body.pagination.offset).toBe(offset);
      view = body.view_sha256;
      await expect(panel.getByText(`Showing ${body.items.length} of ${items.length} scoped results.`)).toBeVisible();
      const rows = await panel.getByRole("row").allTextContents();
      expect(rows.length).toBe(body.items.length + 1);
      for (let index = 0; index < body.items.length; index += 1) {
        const returned = body.items[index];
        const item = originals.get(returned.result_id);
        expect(item).toBeDefined();
        expect(returned.source).toBe("retailops-ai");
        expect(returned.result).toEqual(item);
        expect(seen.has(returned.result_id)).toBe(false);
        seen.add(returned.result_id);
        const row = panel.getByRole("row").nth(index + 1);
        await expect(row.getByRole("cell").nth(0).locator(".identifier-text")).toHaveAttribute("aria-label", item.product_id);
        expect(rows[index + 1]).toContain(item.status);
        if (kind === "anomaly_detected") {
          expect(rows[index + 1]).toContain(item.selling_location_id);
        } else {
          await expect(row.getByRole("cell").nth(1).locator(".identifier-text")).toHaveAttribute("aria-label", item.stock_location_id);
        }
        expect(rows[index + 1]).toContain(item.quality_status);
        if (kind === "stockout_risk_scored") {
          expect(rows[index + 1]).toContain(item.probability === null ? "Unavailable" : `${(item.probability * 100).toFixed(2)}%`);
        }
      }
      if (pages === 0) {
        const first = body.items[0].result;
        await panel.getByRole("button", { name: "View model lineage" }).first().click();
        const lineage = panel.getByRole("region", { name: "Model result lineage" });
        await expect(lineage).toContainText(first[id]);
        await expect(lineage).toContainText(first.release_id);
        await expect(lineage).toContainText(first.inference_run_id);
        await expect(lineage).toContainText((first.lineage || first).source_dataset_id);
        const literal = await request.get(`/api/intelligence/v2/${resource}/${first[id]}`, { headers });
        expect(literal.status()).toBe(200);
        expect((await literal.json()).result).toEqual(first);
      }
      offset = body.pagination.next_offset;
      pages += 1;
      expect(pages).toBeLessThanOrEqual(28);
      if (offset !== null) {
        const nextRead = page.waitForResponse((response) => {
          const url = new URL(response.url());
          return url.pathname === `/api/intelligence/v2/${resource}` && url.searchParams.get("offset") === String(offset);
        });
        await panel.getByRole("button", { name: "Next model page" }).click();
        expect((await nextRead).status()).toBe(200);
        await expect(panel.getByRole("button", { name: `Refresh ${title}` })).toBeEnabled();
      }
    } while (offset !== null);
    expect(seen.size).toBe(originals.size);
    await expect(panel.getByRole("button", { name: "Next model page" })).toHaveCount(0);
    expect((await request.get(`/api/intelligence/v2/${resource}`)).status()).toBe(401);
    expect((await request.get(`/api/intelligence/v2/${resource}?user_id=platform-admin`, { headers })).status()).toBe(422);
    expect((await request.get(`/api/intelligence/v2/${resource}?product_id=ffffffff-ffff-4fff-8fff-ffffffffffff`, { headers })).status()).toBe(403);
    results.push({ kind, rows: seen.size, pages, original_payloads: true, literal_native_id: true, original_lineage_in_UI: true });
  }
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(storage).includes(secret)).toBe(false);
  await page.screenshot({ path: `${process.env.AI10_NATIVE_BROWSER_REPORT}.png`, fullPage: true });
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("retailops:demo-user-changed", { detail: { userId: "platform-admin" } })));
  for (const { title } of cases) {
    const panel = page.getByRole("region", { name: title, exact: true });
    await expect(panel.getByLabel("Personal model read credential")).toHaveValue("");
    await expect(panel.getByRole("table")).toHaveCount(0);
  }
  const policyPath = process.env.AI10_NATIVE_BROWSER_POLICY;
  const policy = JSON.parse(await fs.readFile(policyPath, "utf8"));
  policy.principals[0].credential_sha256 = "0".repeat(64);
  await fs.writeFile(policyPath, JSON.stringify(policy));
  for (const { title } of cases) {
    const panel = page.getByRole("region", { name: title, exact: true });
    await panel.getByLabel("Personal model read credential").fill(secret);
    await panel.getByRole("button", { name: `Connect ${title}` }).click();
    await expect(panel.getByRole("alert")).toContainText("AI model access was denied");
    await expect(panel.getByRole("table")).toHaveCount(0);
  }
  await fs.writeFile(process.env.AI10_NATIVE_BROWSER_REPORT, JSON.stringify({
    status: "passed", scope: "original_native_model_publications_in_built_RetailOps_UI",
    rows: results.reduce((count, result) => count + result.rows, 0), results,
    fixture_fallback: false, credential_storage: false, live_revocation: true,
  }, null, 2));
});
