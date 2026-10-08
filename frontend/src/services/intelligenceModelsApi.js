import { IntelligenceError } from "./intelligenceApi.js";

const resources = {
  anomaly_detected: { path: "anomalies", identity: "anomaly_id", prefix: "anomaly" },
  stockout_risk_scored: { path: "stockout-risks", identity: "risk_id", prefix: "risk" },
};
const messages = {
  401: "AI model access was denied. Reconnect with your personal model read credential.",
  403: "This model result is outside your assigned access scope.",
  404: "This model result is unavailable in your assigned scope.",
  409: "The model history changed. Refresh from the first page.",
  422: "The AI model request is invalid.",
  429: "The model read limit was reached. Narrow the selection or retry later.",
  503: "AI model results are unavailable. Retry later.",
};
const identity = (value, prefix) => typeof value === "string" && new RegExp(`^${prefix}-sha256-[0-9a-f]{64}$`).test(value);

async function read(kind, suffix, credential, signal) {
  const resource = resources[kind];
  if (!resource) throw new IntelligenceError("The model resource is invalid.");
  const location = globalThis.location;
  if (location && location.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)) {
    throw new IntelligenceError("AI model read access requires HTTPS.");
  }
  if (typeof credential !== "string" || !/^[\x21-\x7e]{32,256}$/.test(credential)) {
    throw new IntelligenceError(messages[401], 401);
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  const timer = globalThis.setTimeout(abort, 10_000);
  try {
    const response = await fetch(`/api/intelligence/v2/${resource.path}${suffix}`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${credential}` },
      credentials: "omit", redirect: "error", cache: "no-store", signal: controller.signal,
    });
    if (!response.ok) throw new IntelligenceError(messages[response.status] || "AI model results are unavailable.", response.status);
    const value = await response.json();
    if (controller.signal.aborted) throw new Error("aborted");
    return value;
  } catch (error) {
    if (error instanceof IntelligenceError) throw error;
    throw new IntelligenceError(signal?.aborted ? "AI model request cancelled." : "AI model results could not be read. Retry the request.");
  } finally {
    globalThis.clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

function validateItem(kind, item) {
  const resource = resources[kind];
  const result = item?.result;
  if (!resource || item.source !== "retailops-ai" || item.event_type !== kind
      || !identity(item.result_id, resource.prefix) || result?.[resource.identity] !== item.result_id
      || !["current", "stale", "unknown"].includes(item.freshness?.status)
      || !Number.isFinite(Date.parse(result.generated_at)) || !Number.isFinite(Date.parse(result.as_of))
      || typeof result.product_id !== "string" || !result.inference_run_id || !result.release_id) {
    throw new IntelligenceError("The native AI model result is invalid.");
  }
  if (kind === "stockout_risk_scored") {
    if (!result.stock_location_id || result.horizon_days !== 7
        || !["scored", "already_stockout", "insufficient_data", "stale_input"].includes(result.status)
        || (result.status === "scored"
          ? !(Number.isFinite(result.probability) && result.probability >= 0 && result.probability <= 1 && ["low", "medium", "high", "critical"].includes(result.risk_band))
          : result.probability !== null || result.risk_band !== null)
        || !["passed_at_publication", "mechanics_only"].includes(result.quality_status)) {
      throw new IntelligenceError("The model risk status or probability is invalid.");
    }
  } else if (!result.selling_location_id || !result.channel || !result.currency
      || !["scored", "insufficient_data"].includes(result.status)
      || (result.status === "insufficient_data" && [result.score, result.threshold, result.alert, result.severity].some((value) => value !== null))) {
    throw new IntelligenceError("The anomaly decision status is invalid.");
  }
}

export async function getIntelligenceModels({ kind, credential, offset = 0, view = null, signal }) {
  if (!resources[kind] || !Number.isInteger(offset) || offset < 0 || offset > 10000
      || (offset > 0 && !/^[0-9a-f]{64}$/.test(view || ""))) {
    throw new IntelligenceError("The model page selection is invalid.");
  }
  const query = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (view !== null) query.set("view_sha256", view);
  const page = await read(kind, `?${query}`, credential, signal);
  if (!Array.isArray(page?.items) || page.items.length > 50 || page.selection !== "immutable_history"
      || !/^[0-9a-f]{64}$/.test(page.view_sha256 || "")
      || page.pagination?.offset !== offset || page.pagination.limit !== 50
      || !Number.isInteger(page.pagination.total) || page.pagination.total < 0 || page.pagination.total > 10000
      || page.items.length !== Math.min(50, Math.max(0, page.pagination.total - offset))
      || page.pagination.next_offset !== (offset + 50 < page.pagination.total ? offset + 50 : null)
      || (view !== null && view !== page.view_sha256)) {
    throw new IntelligenceError("The model history response is invalid.");
  }
  page.items.forEach((item) => validateItem(kind, item));
  if (new Set(page.items.map((item) => item.result_id)).size !== page.items.length) {
    throw new IntelligenceError("The model history contains duplicate results.");
  }
  return page;
}

export async function getIntelligenceModel({ kind, credential, resultId, signal }) {
  if (!resources[kind] || !identity(resultId, resources[kind].prefix)) {
    throw new IntelligenceError("The model result identity is invalid.");
  }
  const item = await read(kind, `/${resultId}`, credential, signal);
  validateItem(kind, item);
  if (item.result_id !== resultId) throw new IntelligenceError("The model result identity changed.");
  return item;
}
