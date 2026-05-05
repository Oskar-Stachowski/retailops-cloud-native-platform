import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, apiGet, apiPost, getConfiguredApiBaseUrl, normalizeApiPath, sanitizeBaseUrl, toApiUrl } from "../src/services/apiClient.js";

test("sanitizeBaseUrl removes trailing slashes", () => {
  assert.equal(sanitizeBaseUrl("http://localhost:8000/"), "http://localhost:8000");
  assert.equal(sanitizeBaseUrl("http://localhost:8000///"), "http://localhost:8000");
});

test("getConfiguredApiBaseUrl defaults to same-origin API proxy", () => {
  const originalValue = globalThis.process?.env?.VITE_API_BASE_URL;
  delete globalThis.process.env.VITE_API_BASE_URL;

  try {
    assert.equal(getConfiguredApiBaseUrl(), "/api");
  } finally {
    if (originalValue === undefined) {
      delete globalThis.process.env.VITE_API_BASE_URL;
    } else {
      globalThis.process.env.VITE_API_BASE_URL = originalValue;
    }
  }
});

test("normalizeApiPath always returns a path with leading slash", () => {
  assert.equal(normalizeApiPath("health"), "/health");
  assert.equal(normalizeApiPath("/products"), "/products");
});

test("toApiUrl builds stable backend URL", () => {
  assert.equal(toApiUrl("/health", "http://api:8000/"), "http://api:8000/health");
});

test("apiGet returns parsed JSON response", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  try {
    const data = await apiGet("/health", { baseUrl: "http://localhost:8000" });
    assert.deepEqual(data, { status: "ok" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("apiGet sends GET request to normalized URL", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const data = await apiGet("/health", { baseUrl: "http://localhost:8000/" });

    assert.deepEqual(data, { status: "ok" });
    assert.equal(requests[0].url, "http://localhost:8000/health");
    assert.equal(requests[0].options.method, "GET");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("apiGet throws ApiError for standardized backend error", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: { code: "not_found", message: "Resource not found" } }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });

  try {
    await assert.rejects(
      () => apiGet("/missing", { baseUrl: "http://localhost:8000" }),
      (error) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.status, 404);
        assert.equal(error.code, "not_found");
        assert.equal(error.message, "Resource not found");
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("apiPost sends JSON body and POST method", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ updated: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const data = await apiPost("/notifications/N1/read", { seen: true }, {
      baseUrl: "http://localhost:8000",
    });

    assert.deepEqual(data, { updated: true });
    assert.equal(requests[0].url, "http://localhost:8000/notifications/N1/read");
    assert.equal(requests[0].options.method, "POST");
    assert.equal(requests[0].options.headers["Content-Type"], "application/json");
    assert.equal(requests[0].options.body, JSON.stringify({ seen: true }));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
