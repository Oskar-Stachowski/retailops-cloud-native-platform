import { apiGet, apiGetOptional } from "./apiClient.js";

export const ENDPOINTS = {
  health: ["/health"],
  readiness: ["/ready"],
  dashboardSummary: ["/dashboard/summary", "/dashboard-summary"],
  products: ["/products"],
  forecasts: ["/forecasts"],
  stockRisks: ["/stock-risks", "/inventory-risks", "/inventory-risk"],
  analyticsSummary: ["/analytics/summary", "/analytics"],
  salesSummary: ["/sales/summary", "/sales"],
  inventorySummary: ["/inventory/summary", "/inventory"],
};

export function unwrapPayload(payload) {
  if (!payload) {
    return {};
  }

  if (payload.data && typeof payload.data === "object") {
    return payload.data;
  }

  if (payload.summary && typeof payload.summary === "object") {
    return payload.summary;
  }

  return payload;
}

export function listFromPayload(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (Array.isArray(payload?.items)) {
    return payload.items;
  }

  if (Array.isArray(payload?.data)) {
    return payload.data;
  }

  if (Array.isArray(payload?.results)) {
    return payload.results;
  }

  return [];
}

export function formatSourceStatus(result) {
  if (result.ok) {
    return {
      ok: true,
      label: "connected",
      path: result.path,
      message: "Connected to backend API",
    };
  }

  return {
    ok: false,
    label: "unavailable",
    path: result.path,
    message: result.error?.message || "Endpoint is not available yet",
  };
}

export function normalizeRiskStatus(value) {
  if (!value) {
    return "unknown";
  }

  return String(value).toLowerCase().replace(/\s+/g, "_");
}

function pickNumber(source, keys, fallback = 0) {
  for (const key of keys) {
    const value = source?.[key];

    if (Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return fallback;
}

function countByRisk(items, expectedRisk) {
  return items.filter((item) => {
    const risk = normalizeRiskStatus(
      item.risk_status || item.stock_risk || item.inventory_risk || item.status,
    );

    return risk === expectedRisk;
  }).length;
}

export function buildDashboardSummary(summaryPayload, products, forecasts, stockRisks) {
  const summary = unwrapPayload(summaryPayload);

  return {
    totalProducts: pickNumber(summary, ["total_products", "products_count"], products.length),
    activeProducts: pickNumber(summary, ["active_products", "active_products_count"], products.length),
    forecastRecords: pickNumber(summary, ["forecast_records", "forecasts_count"], forecasts.length),
    stockoutRisks: pickNumber(
      summary,
      ["stockout_risk_count", "stockout_risks", "high_stockout_risk_count"],
      countByRisk(stockRisks, "stockout_risk"),
    ),
    overstockRisks: pickNumber(
      summary,
      ["overstock_risk_count", "overstock_risks"],
      countByRisk(stockRisks, "overstock_risk"),
    ),
    openAlerts: pickNumber(summary, ["open_alerts", "open_alerts_count", "alerts_open"], 0),
    highSeverityAlerts: pickNumber(
      summary,
      ["high_severity_alerts", "critical_alerts", "high_alerts"],
      0,
    ),
    apiLatencyMs: pickNumber(summary, ["api_latency_ms", "latency_ms"], null),
    lastRefreshAt:
      summary.last_refresh_at ||
      summary.last_refreshed_at ||
      summary.last_updated_at ||
      summary.generated_at ||
      null,
  };
}

export async function getHealthStatus(options = {}) {
  return apiGetOptional(ENDPOINTS.health, options);
}

export async function getReadinessStatus(options = {}) {
  return apiGetOptional(ENDPOINTS.readiness, options);
}

export async function getProducts(options = {}) {
  const payload = await apiGet(ENDPOINTS.products[0], options);
  return listFromPayload(payload);
}

export async function getForecasts(options = {}) {
  const payload = await apiGet(ENDPOINTS.forecasts[0], options);
  return listFromPayload(payload);
}

export async function getStockRisks(options = {}) {
  const result = await apiGetOptional(ENDPOINTS.stockRisks, options);

  if (!result.ok) {
    return [];
  }

  return listFromPayload(result.data);
}

export async function getDashboardData(options = {}) {
  const [health, readiness, dashboardSummary, products, forecasts, stockRisks] = await Promise.all([
    apiGetOptional(ENDPOINTS.health, options),
    apiGetOptional(ENDPOINTS.readiness, options),
    apiGetOptional(ENDPOINTS.dashboardSummary, options),
    apiGetOptional(ENDPOINTS.products, options),
    apiGetOptional(ENDPOINTS.forecasts, options),
    apiGetOptional(ENDPOINTS.stockRisks, options),
  ]);

  const productItems = products.ok ? listFromPayload(products.data) : [];
  const forecastItems = forecasts.ok ? listFromPayload(forecasts.data) : [];
  const stockRiskItems = stockRisks.ok ? listFromPayload(stockRisks.data) : [];

  return {
    fetchedAt: new Date().toISOString(),
    summary: buildDashboardSummary(
      dashboardSummary.ok ? dashboardSummary.data : {},
      productItems,
      forecastItems,
      stockRiskItems,
    ),
    products: productItems,
    forecasts: forecastItems,
    stockRisks: stockRiskItems,
    sourceStatus: {
      health: formatSourceStatus(health),
      readiness: formatSourceStatus(readiness),
      dashboardSummary: formatSourceStatus(dashboardSummary),
      products: formatSourceStatus(products),
      forecasts: formatSourceStatus(forecasts),
      stockRisks: formatSourceStatus(stockRisks),
    },
  };
}
