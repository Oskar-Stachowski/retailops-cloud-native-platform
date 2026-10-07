import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { getIntelligenceForecasts, getIntelligenceForecast } from "../src/services/intelligenceApi.js";

const credential = "fixture-personal-read-credential-" + "x".repeat(32);
const forecast = JSON.parse(fs.readFileSync(new URL("../../services/api/app/contracts/intelligence-v2/forecast_generated.fixture.json", import.meta.url))).payload;
const item = { forecast, source: "retailops-ai", freshness: { status: "unknown" } };
const page = { items: [item], heads: [{ valid_until: "2029-01-01T00:00:00Z" }], selection: "approved_release_as_of_run", approval_authority: "private_operator_selection", view_sha256: "a".repeat(64), pagination: { limit: 50, offset: 0, total: 1, next_offset: null } };

test("AI credentials go only to fixed same-origin reads and never follow redirects", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return Response.json(page);
  });
  assert.deepEqual(await getIntelligenceForecasts({ credential }), page);
  assert.equal(calls[0].url, "/api/intelligence/v2/forecasts/active?limit=50&offset=0");
  assert.equal(calls[0].options.headers.Authorization, `Bearer ${credential}`);
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(calls[0].options.cache, "no-store");
});

test("next pages bind the exact view and response position", async (t) => {
  const next = { ...page, items: [item], pagination: { limit: 50, offset: 50, total: 51, next_offset: null } };
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.ok(url.endsWith(`offset=50&view_sha256=${page.view_sha256}`));
    return Response.json(next);
  });
  assert.deepEqual(await getIntelligenceForecasts({ credential, offset: 50, view: page.view_sha256 }), next);
  await assert.rejects(getIntelligenceForecasts({ credential, offset: 50 }), /page selection/);
  next.view_sha256 = "b".repeat(64);
  await assert.rejects(getIntelligenceForecasts({ credential, offset: 50, view: page.view_sha256 }), /selected publication/);
});

test("access failures show fixed messages and discard upstream secret-bearing bodies", async (t) => {
  for (const status of [401, 403, 404, 409, 429, 503]) {
    t.mock.method(globalThis, "fetch", async () => Response.json({ error: { message: credential } }, { status }));
    await assert.rejects(getIntelligenceForecasts({ credential }), (error) => error.status === status && !error.message.includes(credential));
  }
});

test("foreign identities and invalid shapes cannot be shown as scoped AI forecasts", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json(item));
  await assert.rejects(getIntelligenceForecast({ credential, predictionId: "prediction-sha256-" + "0".repeat(64) }), /identity changed/);
  await assert.rejects(getIntelligenceForecast({ credential, predictionId: "https://foreign.invalid/result" }), /identity is invalid/);
  t.mock.method(globalThis, "fetch", async () => Response.json({ ...page, items: [{ ...item, source: "demo" }] }));
  await assert.rejects(getIntelligenceForecasts({ credential }), /response is invalid/);
});

test("slow response bodies remain inside the request deadline", async (t) => {
  t.mock.method(globalThis, "setTimeout", (callback) => { queueMicrotask(callback); return 0; });
  t.mock.method(globalThis, "clearTimeout", () => {});
  t.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => { await Promise.resolve(); return page; } }));
  await assert.rejects(getIntelligenceForecasts({ credential }), /could not be read/);
});

test("a remote plain HTTP origin cannot transmit a personal credential", async (t) => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "location");
  Object.defineProperty(globalThis, "location", { configurable: true, value: { protocol: "http:", hostname: "retailops.example" } });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, "location", original);
    else delete globalThis.location;
  });
  t.mock.method(globalThis, "fetch", () => { throw new Error("must not fetch"); });
  await assert.rejects(getIntelligenceForecasts({ credential }), /requires HTTPS/);
});
