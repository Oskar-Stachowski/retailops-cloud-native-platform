import { expect, test } from "@playwright/test";

const apiBaseURL = process.env.API_BASE_URL || "http://localhost:8000";

test.describe("RetailOps browser smoke", () => {
  test("loads the executive dashboard and product catalog from the local stack", async ({
    page,
    request,
  }) => {
    const healthResponse = await request.get(`${apiBaseURL}/health`);
    expect(healthResponse.ok()).toBeTruthy();

    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "RetailOps executive dashboard" }),
    ).toBeVisible();
    await expect(page.getByLabel("Business KPI metrics")).toContainText("Products");
    await expect(page.getByLabel("Backend integration status")).toContainText(
      "Dashboard summary",
    );
    await expect(
      page.getByRole("heading", {
        name: "Executive dashboard backed by live platform evidence",
      }),
    ).toBeVisible();

    await page.screenshot({
      path: "../ci-cd/reports/e2e/dashboard-smoke-snapshot.png",
      fullPage: true,
    });

    await page.getByRole("link", { name: "Products" }).click();

    await expect(page).toHaveURL(/\/products$/);
    await expect(page.getByRole("heading", { name: "Product catalog" })).toBeVisible();
    await expect(page.getByLabel("Product catalog controls")).toBeVisible();
    await expect(page.getByText("Backend product records")).toBeVisible();
  });
});
