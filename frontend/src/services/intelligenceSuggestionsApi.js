import { IntelligenceError } from "./intelligenceApi.js";

const digest = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const symbol = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const utc = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/;
const text = (value, maximum) => typeof value === "string" && value.length > 0 && value.length <= maximum;
const date = (value) => typeof value === "string" && utc.test(value) && Number.isFinite(Date.parse(value));
const references = (value, minimum) => Array.isArray(value) && value.length >= minimum && value.length <= 8 && value.every((ref) => text(ref, 2048));
const messages = {
  401: "AI suggestion access was denied. Reconnect with your assigned suggestion read credential.",
  403: "This suggestion is outside your assigned AI access scope.",
  404: "This suggestion is unavailable within your assigned AI access scope.",
  409: "The suggestion view changed or expired. Refresh from the first page.",
  422: "The AI suggestion request is invalid.",
  429: "The AI suggestion read limit was reached. Narrow the selection or retry later.",
  503: "AI suggestions are unavailable. Retry later.",
};

async function read(path, credential, signal) {
  const location = globalThis.location;
  if (location && location.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)) {
    throw new IntelligenceError("AI suggestion read access requires HTTPS.");
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
    const response = await fetch(`/api/intelligence/v2/recommendations${path}`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${credential}` },
      credentials: "omit", redirect: "error", cache: "no-store", signal: controller.signal,
    });
    if (!response.ok) throw new IntelligenceError(messages[response.status] || "AI suggestions are unavailable.", response.status);
    const result = await response.json();
    if (controller.signal.aborted) throw new Error("aborted");
    return result;
  } catch (error) {
    if (error instanceof IntelligenceError) throw error;
    throw new IntelligenceError(signal?.aborted ? "AI suggestion request cancelled." : "AI suggestions could not be read. Retry the request.");
  } finally {
    globalThis.clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

function validateItem(item) {
  const suggestion = item?.suggestion;
  const freshness = item?.freshness;
  if (item?.source !== "retailops-ai" || item.execution_authorized !== false || !date(item.received_at)
      || !suggestion || !freshness || freshness.policy_id !== "suggestion-read-v1"
      || suggestion.requires_human_review !== true || suggestion.status !== "proposed"
      || suggestion.freshness_status !== "current" || suggestion.policy_version !== "read-only-review-v1"
      || (suggestion.origin !== undefined && suggestion.origin !== "retailops-ai")
      || !["recommendation_id", "trace_id", "answer_id", "store_id"].every((key) => typeof suggestion[key] === "string" && uuid.test(suggestion[key]))
      || suggestion.store_id !== suggestion.selling_location_id
      || !["product_id", "selling_location_id", "agent_config_version"].every((key) => typeof suggestion[key] === "string" && symbol.test(suggestion[key]))
      || !(suggestion.stock_location_id === null || (typeof suggestion.stock_location_id === "string" && symbol.test(suggestion.stock_location_id)))
      || !["store", "online"].includes(suggestion.channel)
      || !["review_replenishment", "investigate_anomaly", "refresh_source_data"].includes(suggestion.recommendation_type)
      || !["low", "medium", "high"].includes(suggestion.priority)
      || !/^candidate-sha256-[0-9a-f]{64}$/.test(suggestion.candidate_id || "") || !digest.test(suggestion.policy_sha256 || "")
      || !text(suggestion.action, 2000) || !text(suggestion.rationale, 2000) || !text(suggestion.summary, 4000)
      || !references(suggestion.evidence_refs, 1) || !references(suggestion.model_release_refs, 0)
      || ![suggestion.source_as_of, suggestion.created_at, suggestion.expires_at, freshness.evaluated_at, freshness.valid_until].every(date)
      || freshness.valid_until !== suggestion.expires_at) {
    throw new IntelligenceError("The AI suggestion response is invalid.");
  }
  const [source, created, expires, evaluated] = [suggestion.source_as_of, suggestion.created_at, suggestion.expires_at, freshness.evaluated_at].map(Date.parse);
  const status = evaluated >= expires ? "stale" : evaluated < created ? "unknown" : "current";
  const reason = { stale: "suggestion_expired", unknown: "publication_in_future", current: "within_upstream_lifetime" }[status];
  if (created < source || created >= expires || expires - source > 300_000 || freshness.status !== status || freshness.reason !== reason) {
    throw new IntelligenceError("The AI suggestion freshness is invalid.");
  }
}

export async function getIntelligenceSuggestions({ credential, selection = "current", offset = 0, view = null, signal }) {
  if (!["current", "immutable_history"].includes(selection) || !Number.isInteger(offset) || offset < 0 || offset > 500
      || (view !== null && !digest.test(view)) || (offset > 0 && view === null)) {
    throw new IntelligenceError("The AI suggestion page selection is invalid.");
  }
  const query = new URLSearchParams({ selection, limit: "50", offset: String(offset) });
  if (view !== null) query.set("view_sha256", view);
  const page = await read(`?${query}`, credential, signal);
  if (!Array.isArray(page?.items) || page.items.length > 50 || page.selection !== selection
      || page.execution_authorized !== false || !date(page.generated_at) || !digest.test(page.view_sha256 || "")
      || page.pagination?.offset !== offset || page.pagination.limit !== 50
      || !Number.isInteger(page.pagination.total) || page.pagination.total < 0 || page.pagination.total > 500
      || page.items.length !== Math.min(50, Math.max(0, page.pagination.total - offset))
      || page.pagination.next_offset !== (offset + 50 < page.pagination.total ? offset + 50 : null)
      || page.data_status !== (page.pagination.total ? "available" : "no_data")
      || (view !== null && page.view_sha256 !== view)) {
    throw new IntelligenceError("The AI response did not match the selected suggestion view.");
  }
  for (const item of page.items) {
    validateItem(item);
    if (item.freshness.evaluated_at !== page.generated_at || (selection === "current" && item.freshness.status !== "current")) {
      throw new IntelligenceError("The AI suggestion freshness is invalid.");
    }
  }
  if (new Set(page.items.map((item) => item.suggestion.recommendation_id)).size !== page.items.length) {
    throw new IntelligenceError("The AI suggestion response contains duplicate results.");
  }
  return page;
}

export async function getIntelligenceSuggestion({ credential, recommendationId, signal }) {
  if (!uuid.test(recommendationId || "")) throw new IntelligenceError("The suggestion identity is invalid.");
  const item = await read(`/${recommendationId}`, credential, signal);
  validateItem(item);
  if (item.suggestion.recommendation_id !== recommendationId) throw new IntelligenceError("The suggestion identity changed.");
  return item;
}
