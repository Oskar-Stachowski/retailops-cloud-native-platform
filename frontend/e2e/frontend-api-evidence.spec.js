import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const frontendBaseURL = process.env.FRONTEND_BASE_URL || "http://localhost:3000";
const apiBaseURL = process.env.API_BASE_URL || "http://localhost:8000";
const expectLiveOperationsTraffic = process.env.EXPECT_LIVE_OPERATIONS_TRAFFIC !== "0";

const screenshotsDir = path.resolve("../docs/evidence/frontend-api");
const reportsDir = path.resolve("../ci-cd/reports/e2e");
const apiJsonReportPath = path.join(reportsDir, "frontend-api-smoke.json");
const apiTextReportPath = path.join(reportsDir, "frontend-api-smoke.txt");

const fixedApiChecks = [
  { name: "Health", path: "/health" },
  { name: "Readiness", path: "/ready" },
  { name: "Demo users", path: "/users/demo" },
  { name: "Current user", path: "/me?user_id=platform-admin" },
  { name: "Current permissions", path: "/me/permissions?user_id=platform-admin" },
  { name: "Notifications", path: "/notifications?user_id=platform-admin" },
  { name: "Dashboard summary", path: "/dashboard/summary" },
  {
    name: "Dashboard operational visibility",
    path: "/dashboard/operational-visibility?sales_trend_days=30",
  },
  { name: "Dashboard sales trend", path: "/dashboard/sales-trend?days=30" },
  { name: "Dashboard alerts", path: "/dashboard/alerts" },
  { name: "Dashboard recommendations", path: "/dashboard/recommendations" },
  { name: "Dashboard open work items", path: "/dashboard/open-work-items" },
  { name: "Dashboard stock risk summary", path: "/dashboard/stock-risk-summary" },
  {
    name: "Dashboard live operations",
    path: "/dashboard/live-operations?window_minutes=15&recent_events_limit=20&alerts_limit=10",
  },
  { name: "Products", path: "/products?limit=50&offset=0" },
  { name: "Forecasts", path: "/forecasts?limit=50&offset=0" },
  { name: "Inventory risks", path: "/inventory-risks?limit=50&offset=0" },
  { name: "Analytics products", path: "/analytics/products" },
  { name: "Analytics inventory risk", path: "/analytics/inventory-risk" },
  { name: "Sales", path: "/sales?limit=50&offset=0" },
  { name: "Inventory snapshots", path: "/inventory-snapshots?limit=50&offset=0" },
];

const pageEvidence = [
  {
    name: "Dashboard",
    route: "/",
    screenshot: "dashboard.jpg",
    heading: "RetailOps executive dashboard",
  },
  {
    name: "Live operations",
    route: "/live-operations",
    screenshot: "live-operations.jpg",
    heading: "Live operations",
  },
  {
    name: "Products",
    route: "/products",
    screenshot: "products.jpg",
    heading: "Product catalog",
  },
  {
    name: "Forecasts",
    route: "/forecasts",
    screenshot: "forecasts.jpg",
    heading: "Demand forecast foundation",
  },
  {
    name: "Anomalies",
    route: "/anomalies",
    screenshot: "anomalies.jpg",
    heading: "Anomalies",
  },
  {
    name: "Recommendations",
    route: "/recommendations",
    screenshot: "recommendations.jpg",
    heading: "Recommendations",
  },
  {
    name: "Action queue",
    route: "/action-queue",
    screenshot: "action-queue.jpg",
    heading: "Action queue",
  },
  {
    name: "Admin readiness",
    route: "/admin",
    screenshot: "admin-readiness.jpg",
    heading: "Admin readiness",
  },
  {
    name: "Profile",
    route: "/profile",
    screenshot: "profile.jpg",
    heading: "Platform Admin",
  },
];

function truncateBody(body) {
  if (body === null || body === undefined) {
    return null;
  }

  if (typeof body === "string") {
    return body.length > 2_000 ? `${body.slice(0, 2_000)}... [truncated]` : body;
  }

  return body;
}

async function parseResponse(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function callApi(request, check) {
  const startedAt = Date.now();
  const response = await request.get(`${apiBaseURL}${check.path}`);
  const body = await parseResponse(response);

  return {
    name: check.name,
    method: "GET",
    url: `${apiBaseURL}${check.path}`,
    status: response.status(),
    ok: response.ok(),
    duration_ms: Date.now() - startedAt,
    body: truncateBody(body),
  };
}

function firstProductId(productsPayload) {
  const items = Array.isArray(productsPayload?.items)
    ? productsPayload.items
    : Array.isArray(productsPayload?.data)
      ? productsPayload.data
      : [];

  return items[0]?.id || items[0]?.product_id || null;
}

function liveOperationsHasTraffic(payload) {
  const metrics = payload?.metrics || {};
  const statusCounts = payload?.event_status_counts || {};

  return (
    Number(metrics.revenue || 0) > 0 ||
    Number(metrics.units_sold || 0) > 0 ||
    Number(metrics.sales_events || 0) > 0 ||
    Number(metrics.stock_events || 0) > 0 ||
    Number(metrics.anomalies_detected || 0) > 0 ||
    Number(metrics.alerts_created || 0) > 0 ||
    Number(statusCounts.processed || 0) > 0 ||
    Number(statusCounts.total || 0) > 0 ||
    (Array.isArray(payload?.recent_events) && payload.recent_events.length > 0)
  );
}

function toTextReport(results) {
  const lines = [
    "RetailOps frontend/API evidence smoke",
    `Generated at: ${results.generated_at}`,
    `Frontend base URL: ${results.frontend_base_url}`,
    `API base URL: ${results.api_base_url}`,
    "",
    "API checks:",
  ];

  for (const check of results.api_checks) {
    lines.push(
      `- ${check.ok ? "PASS" : "FAIL"} ${check.method} ${check.url} -> ${check.status} (${check.duration_ms}ms)`,
    );
  }

  lines.push("", "Frontend screenshots:");

  for (const screenshot of results.screenshots) {
    lines.push(`- ${screenshot.name}: ${screenshot.route} -> ${screenshot.path}`);
  }

  return `${lines.join("\n")}\n`;
}

async function waitForConnectedPage(page, heading) {
  const headingLocator =
    typeof heading === "string"
      ? page.getByRole("heading", { name: heading, exact: true }).first()
      : page.getByRole("heading", { name: heading }).first();

  await expect(headingLocator).toBeVisible({
    timeout: 15_000,
  });
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
  await page.evaluate(() => document.fonts?.ready).catch(() => {});
  await expect(page.getByText("Backend data unavailable")).toHaveCount(0);
  await expect(page.locator('[role="status"]')).toHaveCount(0);
}

test.describe("RetailOps connected frontend and API evidence", () => {
  test("captures connected page screenshots and representative API outputs", async ({
    page,
    request,
  }) => {
    await fs.mkdir(screenshotsDir, { recursive: true });
    await fs.mkdir(reportsDir, { recursive: true });

    const apiChecks = [...fixedApiChecks];
    const productsResponse = await callApi(request, {
      name: "Products for Product 360 route discovery",
      path: "/products?limit=1&offset=0",
    });
    expect(productsResponse.ok).toBeTruthy();

    const productId = firstProductId(productsResponse.body);

    const pagesToCapture = [...pageEvidence];

    if (productId) {
      apiChecks.push({
        name: "Product 360",
        path: `/products/${productId}/360?limit=10`,
      });
      pagesToCapture.splice(3, 0, {
        name: "Product 360",
        route: `/products/${productId}`,
        screenshot: "product-360.jpg",
        heading: /.+/,
      });
    }

    const apiResults = [productsResponse];

    for (const check of apiChecks) {
      apiResults.push(await callApi(request, check));
    }

    for (const result of apiResults) {
      expect(result.ok, `${result.method} ${result.url} returned ${result.status}`).toBeTruthy();
    }

    const liveOperationsResult = apiResults.find(
      (result) => result.name === "Dashboard live operations",
    );

    if (expectLiveOperationsTraffic) {
      expect(
        liveOperationsHasTraffic(liveOperationsResult?.body),
        "Live Operations evidence requires generated stream/business traffic.",
      ).toBeTruthy();
    }

    const screenshots = [];

    for (const pageSpec of pagesToCapture) {
      await page.goto(pageSpec.route, { waitUntil: "domcontentloaded" });
      await waitForConnectedPage(page, pageSpec.heading);

      const screenshotPath = path.join(screenshotsDir, pageSpec.screenshot);
      await page.screenshot({
        path: screenshotPath,
        fullPage: true,
        type: "jpeg",
        quality: 60,
      });

      screenshots.push({
        name: pageSpec.name,
        route: `${frontendBaseURL}${pageSpec.route}`,
        path: path.relative(path.resolve(".."), screenshotPath),
      });
    }

    const results = {
      generated_at: new Date().toISOString(),
      frontend_base_url: frontendBaseURL,
      api_base_url: apiBaseURL,
      api_checks: apiResults,
      screenshots,
      claim_boundary:
        "Evidence capture proves connected local/CI runtime behavior. It is not visual regression testing and does not assert pixel-perfect UI stability.",
    };

    await fs.writeFile(apiJsonReportPath, `${JSON.stringify(results, null, 2)}\n`);
    await fs.writeFile(apiTextReportPath, toTextReport(results));
  });
});
