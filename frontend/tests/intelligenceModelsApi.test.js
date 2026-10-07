import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { getIntelligenceModels, getIntelligenceModel } from "../src/services/intelligenceModelsApi.js";

const credential = "personal-fixture-model-read-" + "x".repeat(32);
const kinds = ["anomaly_detected", "stockout_risk_scored"];
function item(kind) {
  const event = JSON.parse(readFileSync(new URL(`../../services/api/app/contracts/intelligence-v2/${kind}.fixture.json`, import.meta.url)));
  return { source: "retailops-ai", event_type: kind, result_id: event.payload.anomaly_id || event.payload.risk_id, result: event.payload, freshness: { status: "stale", reason: "origin_age_exceeded" }, received_at: "2026-10-07T12:00:00Z" };
}
function page(kind) {
  return { items: [item(kind)], selection: "immutable_history", view_sha256: "a".repeat(64), pagination: { limit: 50, offset: 0, total: 1, next_offset: null } };
}

for (const kind of kinds) {
  test(`${kind} uses fixed personal scoped reads and preserves the native payload`, async (t) => {
    const previous = globalThis.fetch;
    t.after(() => { globalThis.fetch = previous; });
    const expected = page(kind);
    globalThis.fetch = async (path, options) => {
      assert.ok(path.startsWith(`/api/intelligence/v2/${kind === "anomaly_detected" ? "anomalies" : "stockout-risks"}`));
      assert.equal(options.headers.Authorization, `Bearer ${credential}`);
      assert.equal(options.credentials, "omit");
      assert.equal(options.redirect, "error");
      assert.equal(options.cache, "no-store");
      assert.equal(options.method, undefined);
      return { ok: true, json: async () => expected };
    };
    assert.deepEqual(await getIntelligenceModels({ kind, credential }), expected);
    globalThis.fetch = async () => ({ ok: true, json: async () => expected.items[0] });
    assert.deepEqual(await getIntelligenceModel({ kind, credential, resultId: expected.items[0].result_id }), expected.items[0]);
  });

  test(`${kind} rejects changed identity, duplicate results and invalid pagination`, async (t) => {
    const previous = globalThis.fetch;
    t.after(() => { globalThis.fetch = previous; });
    const example = page(kind);
    for (const change of [
      (value) => { value.items[0].result_id = `${kind === "anomaly_detected" ? "anomaly" : "risk"}-sha256-${"f".repeat(64)}`; },
      (value) => { value.items.push(value.items[0]); value.pagination.total = 2; },
      (value) => { value.pagination.next_offset = 50; },
      (value) => { value.selection = "demo"; },
    ]) {
      const value = structuredClone(example); change(value);
      globalThis.fetch = async () => ({ ok: true, json: async () => value });
      await assert.rejects(getIntelligenceModels({ kind, credential }));
    }
  });
}

test("an unscored model risk cannot invent a probability", async (t) => {
  const previous = globalThis.fetch;
  t.after(() => { globalThis.fetch = previous; });
  const value = page("stockout_risk_scored");
  value.items[0].result.status = "already_stockout";
  value.items[0].result.probability = 0.4;
  globalThis.fetch = async () => ({ ok: true, json: async () => value });
  await assert.rejects(getIntelligenceModels({ kind: "stockout_risk_scored", credential }));
});

test("model access failures discard server bodies and invalid requests send no credentials", async (t) => {
  const previous = globalThis.fetch;
  t.after(() => { globalThis.fetch = previous; });
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return { ok: false, status: 401, json: async () => ({ detail: credential }) };
  };
  await assert.rejects(getIntelligenceModels({ kind: "anomaly_detected", credential }), (error) => error.status === 401 && !error.message.includes(credential));
  for (const options of [{ kind: "demo", credential }, { kind: "anomaly_detected", credential: "short" }, { kind: "anomaly_detected", credential, offset: 50 }]) {
    await assert.rejects(getIntelligenceModels(options));
  }
  assert.equal(calls, 1);
});
