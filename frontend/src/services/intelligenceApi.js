// Personal read credentials stay in the caller's memory. Never use the demo user,
// VITE_API_BASE_URL, cookies, redirects, storage, or service credentials here.
export class IntelligenceError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = "IntelligenceError";
    this.status = status;
  }
}

const safeMessages = {
  401: "AI access was denied. Reconnect with your assigned read credential.",
  403: "This result is outside your AI access scope.",
  404: "This forecast is unavailable within your AI access scope.",
  409: "The publication changed. Refresh from the first page.",
  422: "The AI request is invalid.",
  429: "The AI read limit was reached. Narrow the selection or retry later.",
  503: "AI forecasts are unavailable. Check the selected publication and dependencies.",
};

async function read(path, credential, signal) {
  const location = globalThis.location;
  if (location && location.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)) {
    throw new IntelligenceError("AI read access requires HTTPS.");
  }
  if (typeof credential !== "string" || !/^[\x21-\x7e]{32,256}$/.test(credential)) {
    throw new IntelligenceError(safeMessages[401], 401);
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  const timer = globalThis.setTimeout(abort, 10_000);
  try {
    const response = await fetch(`/api/intelligence/v2/forecasts${path}`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${credential}` },
      credentials: "omit",
      redirect: "error",
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new IntelligenceError(safeMessages[response.status] || "AI forecasts are unavailable.", response.status);
    }
    const value = await response.json();
    if (controller.signal.aborted) throw new Error("aborted");
    return value;
  } catch (error) {
    if (error instanceof IntelligenceError) throw error;
    throw new IntelligenceError(signal?.aborted ? "AI request cancelled." : "AI forecasts could not be read. Retry the request.");
  } finally {
    globalThis.clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export async function getIntelligenceForecasts({ credential, selection = "active", offset = 0, view = null, signal }) {
  if (!["active", "history"].includes(selection) || !Number.isInteger(offset) || offset < 0 || offset > 2800
      || (offset > 0 && !/^[0-9a-f]{64}$/.test(view || ""))) {
    throw new IntelligenceError("The AI page selection is invalid.");
  }
  const query = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (view !== null) query.set("view_sha256", view);
  const page = await read(`${selection === "active" ? "/active" : ""}?${query}`, credential, signal);
  const expected = selection === "active" ? "approved_release_as_of_run" : "immutable_history";
  if (!Array.isArray(page?.items) || page.items.length > 50 || page.selection !== expected
      || !/^[0-9a-f]{64}$/.test(page.view_sha256 || "")
      || page.pagination?.offset !== offset || page.pagination.limit !== 50
      || !Number.isInteger(page.pagination.total) || page.pagination.total < 0 || page.pagination.total > 2800
      || page.items.length !== Math.min(50, Math.max(0, page.pagination.total - offset))
      || page.pagination.next_offset !== (offset + 50 < page.pagination.total ? offset + 50 : null)
      || (view !== null && page.view_sha256 !== view)
      || (selection === "active" && page.approval_authority !== "private_operator_selection")) {
    throw new IntelligenceError("The AI response did not match the selected publication.");
  }
  if (selection === "active" && (!Array.isArray(page.heads) || page.heads.length > 32
      || page.heads.some((head) => !Number.isFinite(Date.parse(head.valid_until))))) {
    throw new IntelligenceError("The selected publication validity is invalid.");
  }
  for (const item of page.items) validateItem(item);
  if (new Set(page.items.map((item) => item.forecast.prediction_id)).size !== page.items.length) {
    throw new IntelligenceError("The AI response contains duplicate results.");
  }
  return page;
}

function validateItem(item) {
  if (item?.source !== "retailops-ai" || !/^prediction-sha256-[0-9a-f]{64}$/.test(item.forecast?.prediction_id || "")
      || !["current", "stale", "unknown"].includes(item.freshness?.status)
      || item.forecast.target_type !== "observed_sales_units" || item.forecast.unit_of_measure !== "unit"
      || !item.forecast.prediction?.candidate || !item.forecast.prediction.baseline || !item.forecast.prediction.metadata) {
    throw new IntelligenceError("The AI forecast response is invalid.");
  }
}

export async function getIntelligenceForecast({ credential, predictionId, signal }) {
  if (!/^prediction-sha256-[0-9a-f]{64}$/.test(predictionId || "")) {
    throw new IntelligenceError("The forecast identity is invalid.");
  }
  const item = await read(`/${predictionId}`, credential, signal);
  validateItem(item);
  if (item.forecast.prediction_id !== predictionId) throw new IntelligenceError("The forecast identity changed.");
  return item;
}
