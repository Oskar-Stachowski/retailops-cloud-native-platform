import { expect, test } from "@playwright/test";
import { apiBaseURL, apiJson, clickMutation, proposedRecommendation } from "./support/api.js";

test.beforeAll(() => {
  expect(process.env.E2E_ALLOW_MUTATIONS, "Run workflow journeys only on a disposable seeded stack with E2E_ALLOW_MUTATIONS=1").toBe("1");
});

test("Product 360 acknowledges and resolves a real alert with persisted audit evidence", async ({ page, request }) => {
  const { items } = await apiJson(request, "/products?limit=100");
  let selected;
  for (const product of items) {
    const detail = await apiJson(request, `/products/${product.id}/360`);
    const alert = detail.alerts.find((item) => item.status === "open");
    if (alert) {
      selected = { product, alert };
      break;
    }
  }
  expect(selected, "Disposable demo seed must contain an open product alert").toBeTruthy();
  const { product, alert } = selected;
  await page.goto(`/products/${product.id}`);
  const alertsTable = page.locator("section.table-card").filter({ has: page.getByRole("heading", { name: "Alerts", exact: true }) });
  const row = alertsTable.getByRole("row").filter({ has: page.getByRole("cell", { name: alert.title, exact: true }) });
  const acknowledged = await clickMutation(page, row.getByRole("button", { name: "Acknowledge" }), `/alerts/${alert.id}/acknowledge`, "acknowledged");
  await page.reload();
  await expect(row.getByRole("cell", { name: "acknowledged", exact: true })).toBeVisible();
  const resolved = await clickMutation(page, row.getByRole("button", { name: "Resolve", exact: true }), `/alerts/${alert.id}/resolve`, "resolved");
  await page.reload();
  await expect(row.getByRole("cell", { name: "resolved", exact: true })).toBeVisible();
  const detail = await apiJson(request, `/products/${product.id}/360?limit=50`);
  expect(detail.alerts.find((item) => item.id === alert.id).status).toBe("resolved");
  for (const result of [acknowledged, resolved]) {
    expect(detail.workflow_actions.filter((item) => item.id === result.workflow_action.id)).toHaveLength(1);
  }
});

test("recommendation remains actionable after acceptance and can be completed", async ({ page, request }) => {
  const recommendation = await proposedRecommendation(request);
  await page.goto("/recommendations");
  await expect(page.getByRole("heading", { name: "Recommendations", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Action Queue", exact: true }).click();
  const row = page.getByTestId(`recommendation-${recommendation.id}`);
  await clickMutation(page, row.getByRole("button", { name: "Accept", exact: true }), `/recommendations/${recommendation.id}/accept`, "accepted");
  await page.reload();
  await expect(row.getByRole("cell", { name: "accepted", exact: true })).toBeVisible();
  await clickMutation(page, row.getByRole("button", { name: "Resolve", exact: true }), `/recommendations/${recommendation.id}/resolve`, "implemented");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Action queue", exact: true })).toBeVisible();
  await expect(row).toHaveCount(0);
  const detail = await apiJson(request, `/products/${recommendation.product_id}/360?limit=50`);
  expect(detail.recommendations.find((item) => item.id === recommendation.id).status).toBe("implemented");
});

test("reject requires a decision comment before persisting the rejection", async ({ page, request }) => {
  const recommendation = await proposedRecommendation(request);
  await page.goto("/action-queue");
  const row = page.getByTestId(`recommendation-${recommendation.id}`);
  const posts = [];
  page.on("request", (outgoing) => {
    if (outgoing.method() === "POST") posts.push(outgoing.url());
  });
  await row.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(page.getByText("Add a decision comment with at least 5 characters.")).toBeVisible();
  expect(posts).toEqual([]);
  await expect(row.getByRole("cell", { name: "proposed", exact: true })).toBeVisible();
  const comment = "E2E review: duplicate replenishment request.";
  await page.getByLabel("Decision comment").fill(comment);
  const result = await clickMutation(page, row.getByRole("button", { name: "Reject", exact: true }), `/recommendations/${recommendation.id}/reject`, "rejected");
  expect(result.workflow_action.comment).toBe(comment);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Action queue", exact: true })).toBeVisible();
  await expect(row).toHaveCount(0);
  const detail = await apiJson(request, `/products/${recommendation.product_id}/360?limit=50`);
  expect(detail.recommendations.find((item) => item.id === recommendation.id).status).toBe("rejected");
});

test("read-only demo user cannot mutate workflow through the UI or API", async ({ page, request }) => {
  const recommendation = await proposedRecommendation(request);
  await page.goto("/action-queue");
  await page.locator(".user-switcher").getByRole("combobox").selectOption("read-only-viewer");
  await expect(page.getByLabel("Action queue summary")).toContainText("Read only");
  const row = page.getByTestId(`recommendation-${recommendation.id}`);
  await expect(row.getByRole("button", { name: "Accept", exact: true })).toBeDisabled();
  await expect(row.getByRole("button", { name: "Reject", exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.locator(".user-switcher").getByRole("combobox")).toHaveValue("read-only-viewer");
  await expect(row.getByRole("button", { name: "Accept", exact: true })).toBeDisabled();
  const response = await request.post(`${apiBaseURL}/recommendations/${recommendation.id}/accept?user_id=read-only-viewer`, { data: {} });
  expect(response.status()).toBe(403);
  const detail = await apiJson(request, `/products/${recommendation.product_id}/360?limit=50`);
  expect(detail.recommendations.find((item) => item.id === recommendation.id).status).toBe("proposed");
});

test("catalog exposes an API failure and Retry restores real backend data", async ({ page }) => {
  const productsURL = (url) => /\/(?:api\/)?products$/.test(url.pathname);
  await page.route(productsURL, (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { message: "Temporary catalog failure" } }) }));
  await page.goto("/products");
  await expect(page.getByRole("alert")).toContainText("Temporary catalog failure");
  await page.unroute(productsURL);
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Backend product records" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open 360" }).first()).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
