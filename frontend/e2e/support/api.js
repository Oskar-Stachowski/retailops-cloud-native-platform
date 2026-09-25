import { expect } from "@playwright/test";

export const apiBaseURL = process.env.API_BASE_URL || "http://localhost:8000";

export async function apiJson(request, path) {
  const response = await request.get(`${apiBaseURL}${path}`);
  expect(response.ok(), `${path}: HTTP ${response.status()}`).toBeTruthy();
  return response.json();
}

export async function proposedRecommendation(request) {
  const { items } = await apiJson(request, "/dashboard/recommendations");
  const record = items.find((item) => item.status === "proposed" && item.product_id);
  expect(record, "Disposable demo seed must contain a proposed recommendation").toBeTruthy();
  return record;
}

export async function clickMutation(page, button, path, status) {
  const responsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(path) && response.request().method() === "POST",
  );
  await button.click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.status).toBe(status);
  expect(result.workflow_action.id).toBeTruthy();
  expect(result.workflow_action.idempotency_key).toBeTruthy();
  return result;
}
