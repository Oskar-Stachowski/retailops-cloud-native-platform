import { expect, test } from "@playwright/test";
import { apiJson } from "./support/api.js";

test("dashboard shows live backend counts and operational sections", async ({ page, request }) => {
  const { summary } = await apiJson(request, "/dashboard/summary");
  expect(summary.products_count).toBeGreaterThan(0);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "RetailOps executive dashboard" })).toBeVisible();
  const productsMetric = page.getByLabel("Business KPI metrics").getByRole("article")
    .filter({ has: page.getByText("Products", { exact: true }) });
  await expect(productsMetric.locator("strong")).toHaveText(String(summary.products_count));
  await expect(page.getByRole("heading", { name: "Operational alerts", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Top recommendations", exact: true })).toBeVisible();
  await expect(page.getByLabel("Backend integration status")).toContainText("Dashboard summary");
  await expect(page.getByRole("heading", { name: "Backend data unavailable" })).toHaveCount(0);
});

test("catalog filters, empty results, reset and Product 360 preserve product identity", async ({ page, request }) => {
  const { items } = await apiJson(request, "/products?limit=1");
  expect(items).toHaveLength(1);
  const product = items[0];
  await page.goto("/");
  await page.getByRole("link", { name: "Products", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Backend product records" })).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search products by SKU, name or brand" });
  await search.fill("__no_such_retailops_product__");
  await expect(page.getByText("No products match the current filters. Clear search or reset filters.")).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(search).toHaveValue("");
  await search.fill(product.sku);
  await page.locator('select[name="category"]').selectOption(product.category);
  const row = page.getByRole("row").filter({ has: page.getByRole("cell", { name: product.sku, exact: true }) });
  await expect(row).toHaveCount(1);
  await row.getByRole("link", { name: "Open 360" }).click();
  await expect(page).toHaveURL(new RegExp(`/products/${product.id}$`));
  await expect(page.getByRole("heading", { name: product.name, exact: true })).toBeVisible();
  await expect(page.getByLabel("Product 360 summary")).toContainText(product.sku);
  await page.reload();
  await expect(page.getByRole("heading", { name: product.name, exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to products" }).click();
  await expect(page).toHaveURL(/\/products$/);
});
