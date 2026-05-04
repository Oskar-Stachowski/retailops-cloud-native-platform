import test from "node:test";
import assert from "node:assert/strict";
import { buildDashboardSummary, listFromPayload, normalizeRiskStatus } from "../src/services/retailopsApi.js";

test("listFromPayload supports direct array payload", () => {
  assert.deepEqual(listFromPayload([{ id: 1 }]), [{ id: 1 }]);
});

test("listFromPayload supports API list response with items key", () => {
  assert.deepEqual(listFromPayload({ items: [{ id: 1 }] }), [{ id: 1 }]);
});

test("normalizeRiskStatus converts labels to stable frontend status", () => {
  assert.equal(normalizeRiskStatus("Stockout Risk"), "stockout_risk");
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
