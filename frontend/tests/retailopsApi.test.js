import test from "node:test";
import assert from "node:assert/strict";
import {
  buildDashboardSummary,
  getProduct360,
  listFromKnownKeys,
  listFromPayload,
  normalizeRiskStatus,
  buildUserScopedPath,
  getCurrentUser,
  getNotifications,
  hasPermission,
  markNotificationRead,
} from "../src/services/retailopsApi.js";

test("listFromPayload supports direct array payload", () => {
  assert.deepEqual(listFromPayload([{ id: 1 }]), [{ id: 1 }]);
});

test("listFromPayload supports API list response with items key", () => {
  assert.deepEqual(listFromPayload({ items: [{ id: 1 }] }), [{ id: 1 }]);
});

test("listFromKnownKeys extracts dashboard-specific collections", () => {
  const payload = {
    data: {
      alerts: [{ id: "A1" }],
    },
  };

  assert.deepEqual(listFromKnownKeys(payload, ["alerts"]), [{ id: "A1" }]);
});

test("normalizeRiskStatus converts labels to stable frontend status", () => {
  assert.equal(normalizeRiskStatus("Stockout Risk"), "stockout_risk");
  assert.equal(normalizeRiskStatus("overstock-risk"), "overstock_risk");
  assert.equal(normalizeRiskStatus(undefined), "unknown");
});

test("buildDashboardSummary uses backend summary first and live endpoint data as fallback", () => {
  const summary = buildDashboardSummary(
    { total_products: 10, stockout_risk_count: 2 },
    [{ sku: "A" }, { sku: "B" }],
    [{ sku: "A", forecast_qty: 20 }],
    [{ sku: "A", risk_status: "stockout_risk" }, { sku: "B", risk_status: "overstock_risk" }],
  );

  assert.equal(summary.totalProducts, 10);
  assert.equal(summary.forecastRecords, 1);
  assert.equal(summary.stockoutRisks, 2);
  assert.equal(summary.overstockRisks, 1);
});

test("buildDashboardSummary derives Sprint 5 operational counters from dashboard payloads", () => {
  const summary = buildDashboardSummary(
    {},
    [{ sku: "A" }, { sku: "B" }],
    [{ product_id: "A" }],
    [
      { sku: "A", risk_status: "stockout_risk" },
      { sku: "B", risk_status: "normal" },
    ],
    {
      alerts: [{ severity: "high" }, { severity: "low" }],
      recommendations: [{ id: "R1" }, { id: "R2" }],
      workItems: [{ id: "W1" }],
      salesTrend: [{ period: "2026-05" }],
    },
  );

  assert.equal(summary.riskyProducts, 1);
  assert.equal(summary.openAlerts, 2);
  assert.equal(summary.highSeverityAlerts, 1);
  assert.equal(summary.recommendationCount, 2);
  assert.equal(summary.openWorkItems, 1);
  assert.equal(summary.salesTrendRecords, 1);
});

test("getProduct360 calls the Product 360 backend endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const requestedUrls = [];

  globalThis.fetch = async (url) => {
    requestedUrls.push(url);
    return new Response(JSON.stringify({ product: { sku: "ELEC-HEAD-001" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const data = await getProduct360("abc", { baseUrl: "http://localhost:8000" });

    assert.equal(requestedUrls[0], "http://localhost:8000/products/abc/360");
    assert.deepEqual(data, { product: { sku: "ELEC-HEAD-001" } });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("buildUserScopedPath adds selected demo user query parameter", () => {
  assert.equal(
    buildUserScopedPath("/me", "inventory-planner"),
    "/me?user_id=inventory-planner",
  );
  assert.equal(
    buildUserScopedPath("/notifications?limit=5", "ops-manager"),
    "/notifications?limit=5&user_id=ops-manager",
  );
});

test("hasPermission supports explicit permissions and platform admin", () => {
  assert.equal(hasPermission(["dashboard:read"], "dashboard:read"), true);
  assert.equal(hasPermission(["platform:admin"], "notifications:write"), true);
  assert.equal(hasPermission([], "platform:admin"), false);
});

test("getCurrentUser calls user-scoped /me endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const requestedUrls = [];

  globalThis.fetch = async (url) => {
    requestedUrls.push(url);
    return new Response(
      JSON.stringify({ user: { id: "ops-manager", role: "operations_manager" } }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    const user = await getCurrentUser({
      baseUrl: "http://localhost:8000",
      userId: "ops-manager",
    });

    assert.equal(requestedUrls[0], "http://localhost:8000/me?user_id=ops-manager");
    assert.deepEqual(user, { id: "ops-manager", role: "operations_manager" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getNotifications calls user-scoped notifications endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const requestedUrls = [];

  globalThis.fetch = async (url) => {
    requestedUrls.push(url);
    return new Response(JSON.stringify({ items: [], unread_count: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const data = await getNotifications({
      baseUrl: "http://localhost:8000",
      userId: "inventory-planner",
    });

    assert.equal(
      requestedUrls[0],
      "http://localhost:8000/notifications?user_id=inventory-planner",
    );
    assert.deepEqual(data, { items: [], unread_count: 0 });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("markNotificationRead calls POST read endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ unread_count: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const data = await markNotificationRead("N1", {
      baseUrl: "http://localhost:8000",
      userId: "platform-admin",
    });

    assert.equal(
      requests[0].url,
      "http://localhost:8000/notifications/N1/read?user_id=platform-admin",
    );
    assert.equal(requests[0].options.method, "POST");
    assert.deepEqual(data, { unread_count: 0 });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
