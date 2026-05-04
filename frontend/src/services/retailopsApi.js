import { apiGet, apiGetOptional } from "./apiClient.js";

export const ENDPOINTS = {
  health: ["/health"],
  readiness: ["/ready"],
  dashboardSummary: ["/dashboard/summary", "/dashboard-summary"],
  dashboardOperationalVisibility: ["/dashboard/operational-visibility"],
  dashboardSalesTrend: ["/dashboard/sales-trend"],
  dashboardAlerts: ["/dashboard/alerts"],
  dashboardRecommendations: ["/dashboard/recommendations"],
  dashboardOpenWorkItems: ["/dashboard/open-work-items"],
  dashboardStockRiskSummary: ["/dashboard/stock-risk-summary"],
  products: ["/products"],
  product360: (productId) => `/products/${productId}/360`,
  forecasts: ["/forecasts"],
  stockRisks: ["/inventory-risks", "/stock-risks", "/inventory-risk"],
  analyticsProducts: ["/analytics/products"],
  analyticsInventoryRisk: ["/analytics/inventory-risk"],
  sales: ["/sales"],
  inventorySnapshots: ["/inventory-snapshots"],
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

export function listFromKnownKeys(payload, keys = []) {
  const unwrapped = unwrapPayload(payload);

  if (Array.isArray(unwrapped)) {
    return unwrapped;
  }

  for (const key of keys) {
    if (Array.isArray(unwrapped?.[key])) {
      return unwrapped[key];
    }
  }

  return listFromPayload(unwrapped);
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

  return String(value).toLowerCase().replace(/[-\s]+/g, "_");
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

function countRiskyProducts(stockRisks) {
  return stockRisks.filter((item) => {
    const risk = normalizeRiskStatus(
      item.risk_status || item.stock_risk || item.inventory_risk || item.status,
    );

    return risk !== "normal" && risk !== "unknown";
  }).length;
}

export function buildDashboardSummary(
  summaryPayload,
  products,
  forecasts,
  stockRisks,
  operationalPayloads = {},
) {
  const summary = unwrapPayload(summaryPayload);
  const {
    alerts = [],
    recommendations = [],
    workItems = [],
    stockRiskSummary = {},
    salesTrend = [],
  } = operationalPayloads;

  return {
    totalProducts: pickNumber(summary, ["total_products", "products_count"], products.length),
    activeProducts: pickNumber(
      summary,
      ["active_products", "active_products_count"],
      products.length,
    ),
    forecastRecords: pickNumber(
      summary,
      ["forecast_records", "forecasts_count"],
      forecasts.length,
    ),
    stockoutRisks: pickNumber(
      { ...stockRiskSummary, ...summary },
      ["stockout_risk_count", "stockout_risks", "high_stockout_risk_count"],
      countByRisk(stockRisks, "stockout_risk"),
    ),
    overstockRisks: pickNumber(
      { ...stockRiskSummary, ...summary },
      ["overstock_risk_count", "overstock_risks"],
      countByRisk(stockRisks, "overstock_risk"),
    ),
    riskyProducts: pickNumber(
      { ...stockRiskSummary, ...summary },
      ["risky_products", "risky_product_count", "total_risky_products"],
      countRiskyProducts(stockRisks),
    ),
    anomalyCount: pickNumber(
      summary,
      ["anomaly_count", "anomalies_count", "open_anomalies"],
      0,
    ),
    recommendationCount: pickNumber(
      summary,
      ["recommendation_count", "recommendations_count", "open_recommendations"],
      recommendations.length,
    ),
    openAlerts: pickNumber(
      summary,
      ["open_alerts", "open_alerts_count", "alerts_open"],
      alerts.length,
    ),
    highSeverityAlerts: pickNumber(
      summary,
      ["high_severity_alerts", "critical_alerts", "high_alerts"],
      alerts.filter((item) => ["critical", "high"].includes(String(item.severity).toLowerCase()))
        .length,
    ),
    openWorkItems: pickNumber(
      summary,
      ["open_work_items", "open_work_items_count", "work_items_open"],
      workItems.length,
    ),
    salesTrendRecords: salesTrend.length,
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

export async function getProduct360(productId, options = {}) {
  if (!productId) {
    throw new Error("Product id is required to load Product 360.");
  }

  return apiGet(ENDPOINTS.product360(productId), options);
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
  const [
    health,
    readiness,
    dashboardSummary,
    operationalVisibility,
    salesTrend,
    alerts,
    recommendations,
    openWorkItems,
    stockRiskSummary,
    products,
    forecasts,
    stockRisks,
  ] = await Promise.all([
    apiGetOptional(ENDPOINTS.health, options),
    apiGetOptional(ENDPOINTS.readiness, options),
    apiGetOptional(ENDPOINTS.dashboardSummary, options),
    apiGetOptional(ENDPOINTS.dashboardOperationalVisibility, options),
    apiGetOptional(ENDPOINTS.dashboardSalesTrend, options),
    apiGetOptional(ENDPOINTS.dashboardAlerts, options),
    apiGetOptional(ENDPOINTS.dashboardRecommendations, options),
    apiGetOptional(ENDPOINTS.dashboardOpenWorkItems, options),
    apiGetOptional(ENDPOINTS.dashboardStockRiskSummary, options),
    apiGetOptional(ENDPOINTS.products, options),
    apiGetOptional(ENDPOINTS.forecasts, options),
    apiGetOptional(ENDPOINTS.stockRisks, options),
  ]);

  const productItems = products.ok ? listFromPayload(products.data) : [];
  const forecastItems = forecasts.ok ? listFromPayload(forecasts.data) : [];
  const stockRiskItems = stockRisks.ok ? listFromPayload(stockRisks.data) : [];
  const salesTrendItems = salesTrend.ok
    ? listFromKnownKeys(salesTrend.data, ["sales_trend", "trend", "records", "items"])
    : [];
  const alertItems = alerts.ok ? listFromKnownKeys(alerts.data, ["alerts", "items"]) : [];
  const recommendationItems = recommendations.ok
    ? listFromKnownKeys(recommendations.data, ["recommendations", "items"])
    : [];
  const workItems = openWorkItems.ok
    ? listFromKnownKeys(openWorkItems.data, ["open_work_items", "work_items", "items"])
    : [];
  const stockRiskSummaryData = stockRiskSummary.ok ? unwrapPayload(stockRiskSummary.data) : {};
  const operationalVisibilityData = operationalVisibility.ok
    ? unwrapPayload(operationalVisibility.data)
    : {};

  return {
    fetchedAt: new Date().toISOString(),
    summary: buildDashboardSummary(
      dashboardSummary.ok ? dashboardSummary.data : {},
      productItems,
      forecastItems,
      stockRiskItems,
      {
        alerts: alertItems,
        recommendations: recommendationItems,
        workItems,
        stockRiskSummary: stockRiskSummaryData,
        salesTrend: salesTrendItems,
      },
    ),
    products: productItems,
    forecasts: forecastItems,
    stockRisks: stockRiskItems,
    salesTrend: salesTrendItems,
    alerts: alertItems,
    recommendations: recommendationItems,
    openWorkItems: workItems,
    stockRiskSummary: stockRiskSummaryData,
    operationalVisibility: operationalVisibilityData,
    sourceStatus: {
      health: formatSourceStatus(health),
      readiness: formatSourceStatus(readiness),
      dashboardSummary: formatSourceStatus(dashboardSummary),
      operationalVisibility: formatSourceStatus(operationalVisibility),
      salesTrend: formatSourceStatus(salesTrend),
      alerts: formatSourceStatus(alerts),
      recommendations: formatSourceStatus(recommendations),
      openWorkItems: formatSourceStatus(openWorkItems),
      stockRiskSummary: formatSourceStatus(stockRiskSummary),
      products: formatSourceStatus(products),
      forecasts: formatSourceStatus(forecasts),
      stockRisks: formatSourceStatus(stockRisks),
    },
  };
}
