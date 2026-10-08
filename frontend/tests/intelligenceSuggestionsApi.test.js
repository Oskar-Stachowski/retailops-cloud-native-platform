import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { getIntelligenceSuggestion, getIntelligenceSuggestions } from "../src/services/intelligenceSuggestionsApi.js";

const credential = "fixture-suggestion-read-credential-" + "x".repeat(32);
const suggestion = JSON.parse(fs.readFileSync(new URL("../../services/api/app/contracts/intelligence-suggestions-v1/recommendation_generated.fixture.json", import.meta.url))).payload;
const item = { suggestion, source: "retailops-ai", received_at: suggestion.created_at, execution_authorized: false,
  freshness: { status: "current", reason: "within_upstream_lifetime", evaluated_at: suggestion.created_at,
    valid_until: suggestion.expires_at, policy_id: "suggestion-read-v1" } };
const page = { items: [item], selection: "current", view_sha256: "a".repeat(64), generated_at: suggestion.created_at,
  data_status: "available", execution_authorized: false, pagination: { limit: 50, offset: 0, total: 1, next_offset: null } };

test("suggestion capability uses fixed same-origin GET with no cookies, storage or redirects", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/intelligence/v2/recommendations?selection=current&limit=50&offset=0");
    assert.equal(options.headers.Authorization, `Bearer ${credential}`);
    assert.equal(options.credentials, "omit");
    assert.equal(options.redirect, "error");
    assert.equal(options.cache, "no-store");
    return Response.json(page);
  });
  assert.deepEqual(await getIntelligenceSuggestions({ credential }), page);
});

test("suggestion history keeps expired original payload and distinct read freshness", async (t) => {
  const stale = structuredClone(item);
  stale.freshness = { ...stale.freshness, status: "stale", reason: "suggestion_expired", evaluated_at: suggestion.expires_at };
  const history = { ...page, selection: "immutable_history", generated_at: suggestion.expires_at, items: [stale] };
  t.mock.method(globalThis, "fetch", async () => Response.json(history));
  assert.deepEqual((await getIntelligenceSuggestions({ credential, selection: "immutable_history" })).items[0].suggestion, suggestion);
  t.mock.method(globalThis, "fetch", async () => Response.json({ ...history, selection: "current" }));
  await assert.rejects(getIntelligenceSuggestions({ credential }), /freshness is invalid/);
});

test("suggestion pages enforce the bound view, count, position and unique identities", async (t) => {
  const next = { ...page, pagination: { limit: 50, offset: 50, total: 51, next_offset: null } };
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.ok(url.endsWith(`offset=50&view_sha256=${page.view_sha256}`));
    return Response.json(next);
  });
  assert.deepEqual(await getIntelligenceSuggestions({ credential, offset: 50, view: page.view_sha256 }), next);
  await assert.rejects(getIntelligenceSuggestions({ credential, offset: 50 }), /page selection/);
  for (const change of [{ view_sha256: "b".repeat(64) }, { pagination: { ...next.pagination, total: 501 } }]) {
    t.mock.method(globalThis, "fetch", async () => Response.json({ ...next, ...change }));
    await assert.rejects(getIntelligenceSuggestions({ credential, offset: 50, view: page.view_sha256 }), /selected suggestion view/);
  }
  t.mock.method(globalThis, "fetch", async () => Response.json({ ...page, items: [item, item], pagination: { ...page.pagination, total: 2 } }));
  await assert.rejects(getIntelligenceSuggestions({ credential }), /duplicate results/);
});

test("malformed review permissions, identities, evidence and lifetime fail closed", async (t) => {
  const mutations = [
    (v) => { v.execution_authorized = true; },
    (v) => { v.suggestion.requires_human_review = "true"; },
    (v) => { v.suggestion.status = "approved"; },
    (v) => { v.suggestion.evidence_refs = []; },
    (v) => { v.suggestion.model_release_refs = [null]; },
    (v) => { v.suggestion.summary = {}; },
    (v) => { v.suggestion.store_id = "22345678-1234-4234-8234-123456789012"; },
    (v) => { v.freshness.status = "stale"; },
    (v) => { v.suggestion.expires_at = "2026-10-04T18:05:01Z"; v.freshness.valid_until = v.suggestion.expires_at; },
    (v) => { v.freshness.valid_until = "2030-01-01T00:00:00Z"; },
    (v) => { v.freshness.evaluated_at = "not-a-date"; },
  ];
  for (const mutate of mutations) {
    const invalid = structuredClone(item);
    mutate(invalid);
    t.mock.method(globalThis, "fetch", async () => Response.json(invalid));
    await assert.rejects(getIntelligenceSuggestion({ credential, recommendationId: suggestion.recommendation_id }), /invalid/);
  }
});

test("suggestion detail identity cannot change and error bodies cannot reveal secrets", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json(item));
  await assert.rejects(getIntelligenceSuggestion({ credential, recommendationId: suggestion.trace_id }), /identity changed/);
  await assert.rejects(getIntelligenceSuggestion({ credential, recommendationId: "https://other.invalid/read" }), /identity is invalid/);
  for (const status of [401, 403, 404, 409, 422, 429, 503]) {
    t.mock.method(globalThis, "fetch", async () => Response.json({ detail: credential }, { status }));
    await assert.rejects(getIntelligenceSuggestions({ credential }), (error) => error.status === status && !error.message.includes(credential));
  }
});

test("cancellation and slow suggestion bodies remain within the deadline", async (t) => {
  const controller = new AbortController();
  controller.abort();
  t.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => page }));
  await assert.rejects(getIntelligenceSuggestions({ credential, signal: controller.signal }), /cancelled/);
  t.mock.method(globalThis, "setTimeout", (callback) => { queueMicrotask(callback); return 0; });
  t.mock.method(globalThis, "clearTimeout", () => {});
  await assert.rejects(getIntelligenceSuggestions({ credential }), /could not be read/);
});

test("remote HTTP and invalid suggestion credentials cannot transmit a secret", async (t) => {
  t.mock.method(globalThis, "fetch", () => { throw new Error("must not fetch"); });
  await assert.rejects(getIntelligenceSuggestions({ credential: "short" }), /access was denied/);
  const original = Object.getOwnPropertyDescriptor(globalThis, "location");
  Object.defineProperty(globalThis, "location", { configurable: true, value: { protocol: "http:", hostname: "retailops.example" } });
  t.after(() => { if (original) Object.defineProperty(globalThis, "location", original); else delete globalThis.location; });
  await assert.rejects(getIntelligenceSuggestions({ credential }), /requires HTTPS/);
});
