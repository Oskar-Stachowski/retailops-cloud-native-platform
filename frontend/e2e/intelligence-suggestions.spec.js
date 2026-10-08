import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

test("personal read-only suggestions, evidence, history, expiry and cancellation", async ({ page, request }) => {
  const root = process.env.INTELLIGENCE_UI_CONTROL_DIR;
  if (!root) throw new Error("The owned disposable intelligence UI drill must prepare this test.");
  const secret = await fs.readFile(path.join(root, "suggestion-credential"), "utf8");
  const forecastSecret = await fs.readFile(path.join(root, "credential"), "utf8");
  const expected = JSON.parse(await fs.readFile(path.join(root, "suggestion-expected.json"), "utf8"));
  const historical = JSON.parse(await fs.readFile(path.join(root, "suggestion-history.json"), "utf8"));
  const panel = page.getByRole("region", { name: "AI suggestions", exact: true });
  const headers = { Authorization: `Bearer ${secret}` };
  const assertions = [];
  // Hold an actual legacy response until after AI connects. Completing that
  // independent dashboard load must preserve the AI panel's component identity.
  let releaseContext;
  let contextEntered;
  const contextBlocked = new Promise((resolve) => { releaseContext = resolve; });
  const contextIntercepted = new Promise((resolve) => { contextEntered = resolve; });
  await page.route("**/api/dashboard/operational-visibility?**", async (route) => {
    const response = await route.fetch();
    contextEntered();
    await contextBlocked;
    await route.fulfill({ response });
  });
  // A workstation eight years behind must not extend the server's validity.
  await page.addInitScript(() => { Date.now = () => Date.parse("2018-01-01T00:00:00Z"); });
  async function connect() {
    await panel.getByLabel("Personal suggestion read credential").fill(secret);
    await panel.getByRole("button", { name: "Connect AI suggestions" }).click();
    await expect(panel.getByRole("heading", { name: "AI suggestion results" })).toBeVisible();
  }
  await page.goto("/recommendations");
  await expect(panel.getByLabel("Personal suggestion read credential")).toBeVisible();
  await expect(panel.getByRole("table")).toHaveCount(0);
  const anonymous = await request.get("/api/intelligence/v2/recommendations?user_id=platform-admin");
  expect(anonymous.status()).toBe(401);
  expect(anonymous.headers()["cache-control"]).toBe("no-store");
  const wrongCapability = await request.get("/api/intelligence/v2/recommendations", { headers: { Authorization: `Bearer ${forecastSecret}` } });
  expect(wrongCapability.status()).toBe(401);
  const foreign = await request.get("/api/intelligence/v2/recommendations?product_id=foreign-suggestion-product", { headers });
  expect(foreign.status()).toBe(403);
  const override = await request.get("/api/intelligence/v2/recommendations?user_id=platform-admin", { headers });
  expect(override.status()).toBe(422);
  const firstResponse = await request.get("/api/intelligence/v2/recommendations?selection=current&limit=50&offset=0", { headers });
  expect(firstResponse.ok()).toBeTruthy();
  expect(firstResponse.headers()["cache-control"]).toBe("no-store");
  const first = await firstResponse.json();
  expect(first.items.map((item) => item.suggestion)).toEqual(expected.slice(0, 50));
  expect(first.execution_authorized).toBe(false);

  await connect();
  await contextIntercepted;
  await expect(page.getByText("Loading recommendation context", { exact: true })).toBeVisible();
  releaseContext();
  await page.unrouteAll({ behavior: "wait" });
  await expect(page.getByText("Loading recommendation context", { exact: true })).toHaveCount(0);
  await expect(panel.getByRole("heading", { name: "AI suggestion results" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Disconnect AI suggestions" })).toBeVisible();
  assertions.push("completed actual legacy dashboard response preserves connected AI panel and data");
  await expect(panel.getByText("Showing 50 of 70 scoped suggestions.")).toBeVisible();
  const rows = await panel.getByRole("row").allTextContents();
  expect(rows.length).toBe(51);
  for (let index = 0; index < 50; index += 1) {
    expect(rows[index + 1]).toContain(expected[index].product_id);
    expect(rows[index + 1]).toContain(expected[index].action);
    expect(rows[index + 1]).toContain(expected[index].expires_at);
  }
  await panel.getByRole("button", { name: "View suggestion evidence" }).first().click();
  const evidence = panel.getByRole("region", { name: "Suggestion evidence" });
  for (const key of ["recommendation_id", "candidate_id", "trace_id", "answer_id", "rationale", "summary", "policy_sha256", "agent_config_version", "source_as_of", "expires_at"]) {
    await expect(evidence).toContainText(expected[0][key]);
  }
  for (const reference of [...expected[0].evidence_refs, ...expected[0].model_release_refs]) await expect(evidence).toContainText(reference);
  await expect(evidence).toContainText("Execution is not authorized");
  await expect(evidence.locator("script, a")).toHaveCount(0);
  expect(await page.evaluate(() => window.fixtureLeak === undefined)).toBe(true);
  await expect(panel.getByRole("button", { name: /accept|execute|approve|reject/i })).toHaveCount(0);
  await expect(panel.locator('input[type="password"]')).toHaveCount(0);
  await panel.screenshot({ path: path.join(root, "suggestion-evidence.png") });
  await panel.getByRole("button", { name: "Next suggestion page" }).click();
  await expect(panel.getByText("Showing 20 of 70 scoped suggestions.")).toBeVisible();
  await expect(panel).not.toContainText("foreign-suggestion-product");
  await expect(panel).not.toContainText("foreign:model");
  assertions.push("exact scoped payload, full evidence, escaped references, no execution controls, 50/20 pagination");

  await panel.getByLabel("Suggestion view").selectOption("immutable_history");
  await expect(panel.getByText("Showing 50 of 72 scoped suggestions.")).toBeVisible();
  await expect(panel).toContainText("unknown");
  await panel.getByRole("button", { name: "Next suggestion page" }).click();
  await expect(panel.getByText("Showing 22 of 72 scoped suggestions.")).toBeVisible();
  const expiredRow = panel.getByRole("row").filter({ hasText: historical[0].expires_at });
  await expect(expiredRow).toContainText("stale");
  await expiredRow.getByRole("button", { name: "View suggestion evidence" }).click();
  await expect(evidence).toContainText("stale: suggestion_expired");
  const original = await request.get(`/api/intelligence/v2/recommendations/${historical[0].recommendation_id}`, { headers });
  expect((await original.json()).suggestion).toEqual(historical[0]);
  assertions.push("72 scoped historical results retain original expired/future payloads with separate stale/unknown read freshness");

  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(storage).includes(secret)).toBe(false);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("retailops:demo-user-changed", { detail: { userId: "platform-admin" } })));
  await expect(panel.getByLabel("Personal suggestion read credential")).toHaveValue("");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await connect();
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
    delete document.visibilityState;
  });
  await expect(panel.getByLabel("Personal suggestion read credential")).toHaveValue("");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await connect();
  let release;
  let entered;
  const blocked = new Promise((resolve) => { release = resolve; });
  const intercepted = new Promise((resolve) => { entered = resolve; });
  await page.route("**/api/intelligence/v2/recommendations?**", async (route) => {
    const response = await route.fetch();
    entered();
    await blocked;
    try { await route.fulfill({ response }); } catch { /* disconnected request is cancelled */ }
  });
  await panel.getByRole("button", { name: "Refresh AI suggestions" }).click();
  await intercepted;
  await panel.getByRole("button", { name: "Disconnect AI suggestions" }).click();
  release();
  await page.unrouteAll({ behavior: "wait" });
  await expect(panel.getByRole("table")).toHaveCount(0);
  await connect();
  assertions.push("no credential storage; demo switch and synthetic hidden event clear memory; completed in-flight read cannot restore a disconnected panel");

  const policyPath = path.join(root, "suggestion-access.json");
  const policy = JSON.parse(await fs.readFile(policyPath, "utf8"));
  await fs.writeFile(policyPath, JSON.stringify({ ...policy, principals: [{ ...policy.principals[0], credential_sha256: "0".repeat(64) }] }));
  await panel.getByRole("button", { name: "Refresh AI suggestions" }).click();
  await expect(panel.getByRole("alert")).toContainText("AI suggestion access was denied");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByLabel("Personal suggestion read credential")).toHaveValue("");
  await fs.writeFile(policyPath, JSON.stringify(policy));
  await connect();
  assertions.push("running API re-reads personal suggestion policy; revocation removes results with no restart");

  // Project a new actual PG fixture only now, so its expiry is independent of CI startup.
  const short = JSON.parse(execFileSync(process.env.INTELLIGENCE_UI_PYTHON, ["scripts/intelligence-ui/suggestion_fixture.py"], { cwd: path.resolve(".."), env: process.env, encoding: "utf8" }));
  const changed = await request.get(`/api/intelligence/v2/recommendations?selection=current&limit=50&offset=50&view_sha256=${first.view_sha256}`, { headers });
  expect(changed.status()).toBe(409);
  await panel.getByRole("button", { name: "Refresh AI suggestions" }).click();
  await expect(panel.getByText("Showing 50 of 71 scoped suggestions.")).toBeVisible();
  await panel.getByRole("button", { name: "View suggestion evidence" }).first().click();
  await expect(evidence).toContainText(short.recommendation_id);
  await expect(panel.getByRole("alert")).toContainText("A suggestion expired", { timeout: 12_000 });
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(evidence).toHaveCount(0);
  await panel.getByRole("button", { name: "Refresh AI suggestions" }).click();
  await expect(panel.getByText("Showing 50 of 70 scoped suggestions.")).toBeVisible();
  const stale = await request.get(`/api/intelligence/v2/recommendations/${short.recommendation_id}`, { headers });
  const staleBody = await stale.json();
  expect(staleBody.suggestion).toEqual(short);
  expect(staleBody.freshness.status).toBe("stale");
  expect(staleBody.execution_authorized).toBe(false);
  assertions.push("new publication rejects old digest; actual short expiry clears page and evidence despite workstation clock skew; immutable detail remains stale");
  await panel.getByRole("button", { name: "Disconnect AI suggestions" }).click();
  await fs.writeFile(path.join(root, "suggestion-browser-report.json"), JSON.stringify({ status: "passed", anonymous: 401, forecast_capability: 401, foreign_scope: 403, user_id_override: 422, changed_view: 409, current_counts: [50, 20], history_count: 72, short_expiry_database_evaluated: true, clock_skew_tested: true, assertions }));
});
