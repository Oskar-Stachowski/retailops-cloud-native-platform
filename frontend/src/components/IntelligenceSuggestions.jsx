import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeDemoUserChanged } from "../auth/demoUser.js";
import { getIntelligenceSuggestion, getIntelligenceSuggestions } from "../services/intelligenceSuggestionsApi.js";
import DataTable from "./DataTable.jsx";
import StatusBadge from "./StatusBadge.jsx";
import "../styles/intelligence-forecasts.css";

const initial = { loading: false, error: null, page: null, detail: null, expiresAt: null };
const columns = [
  { header: "Product / selling location / channel", accessor: ({ suggestion: s }) => `${s.product_id} / ${s.selling_location_id} / ${s.channel}` },
  { header: "Review type / priority", accessor: ({ suggestion: s }) => `${s.recommendation_type} / ${s.priority}` },
  { header: "Proposed action", accessor: ({ suggestion }) => suggestion.action },
  { header: "Expires (UTC)", accessor: ({ suggestion }) => suggestion.expires_at },
  { header: "Freshness", render: ({ freshness }) => <span><StatusBadge status={freshness.status} /> {freshness.reason}</span> },
];

function Evidence({ item }) {
  const s = item.suggestion;
  return (
    <section className="ai-forecast-lineage" aria-label="Suggestion evidence">
      <h3>Suggestion evidence</h3>
      <p>Human review required. Execution is not authorized.</p>
      <dl>
        {[
          ["Suggestion", s.recommendation_id], ["Candidate", s.candidate_id],
          ["Trace", s.trace_id], ["Answer", s.answer_id], ["Source", item.source],
          ["Product", s.product_id], ["Selling location", s.selling_location_id],
          ["Stock location", s.stock_location_id ?? "Unavailable"], ["Channel", s.channel],
          ["Review type", s.recommendation_type], ["Priority", s.priority],
          ["Proposed action", s.action], ["Rationale", s.rationale], ["Summary", s.summary],
          ["Policy version", s.policy_version], ["Policy checksum", s.policy_sha256],
          ["Agent configuration", s.agent_config_version], ["Status", s.status],
          ["Source as of (UTC)", s.source_as_of], ["Created (UTC)", s.created_at],
          ["Expires (UTC)", s.expires_at], ["Received (UTC)", item.received_at],
          ["Freshness at publication", s.freshness_status],
          ["Freshness at read", `${item.freshness.status}: ${item.freshness.reason}`],
          ["Evaluated at (UTC)", item.freshness.evaluated_at],
        ].map(([name, content]) => <div key={name}><dt>{name}</dt><dd>{content}</dd></div>)}
        <div><dt>Evidence references</dt><dd><ul>{s.evidence_refs.map((ref, index) => <li key={index}>{ref}</li>)}</ul></dd></div>
        <div><dt>Model release references</dt><dd>{s.model_release_refs.length ? <ul>{s.model_release_refs.map((ref, index) => <li key={index}>{ref}</li>)}</ul> : "None supplied"}</dd></div>
      </dl>
    </section>
  );
}

// Use the server's evaluated clock and subtract the entire request duration.
// A skewed workstation clock cannot extend the upstream validity window.
function deadline(items, started) {
  const remaining = items.filter((item) => item.freshness.status === "current")
    .map((item) => Date.parse(item.suggestion.expires_at) - Date.parse(item.freshness.evaluated_at));
  return remaining.length ? started + Math.min(...remaining) : null;
}

export default function IntelligenceSuggestions() {
  const [credential, setCredential] = useState("");
  const [selection, setSelection] = useState("current");
  const [state, setState] = useState(initial);
  const input = useRef(null);
  const request = useRef(null);
  const generation = useRef(0);
  const clear = useCallback(() => {
    generation.current += 1;
    request.current?.abort();
    setCredential("");
    setSelection("current");
    setState(initial);
    if (input.current) input.current.value = "";
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeDemoUserChanged(clear);
    const hide = () => { if (document.visibilityState === "hidden") clear(); };
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("pagehide", clear);
    return () => {
      generation.current += 1;
      request.current?.abort();
      unsubscribe();
      document.removeEventListener("visibilitychange", hide);
      window.removeEventListener("pagehide", clear);
    };
  }, [clear]);

  useEffect(() => {
    if (!credential) return;
    const timer = window.setTimeout(clear, 5 * 60 * 1000);
    return () => window.clearTimeout(timer);
  }, [credential, clear]);

  useEffect(() => {
    if (state.expiresAt === null) return;
    const timer = window.setTimeout(() => {
      generation.current += 1;
      request.current?.abort();
      setState({ ...initial, error: "A suggestion expired. Refresh AI suggestions to re-evaluate freshness." });
    }, Math.max(0, state.expiresAt - performance.now()));
    return () => window.clearTimeout(timer);
  }, [state.expiresAt]);

  async function load({ secret = credential, mode = selection, offset = 0, view = null, recommendationId = null } = {}) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const version = ++generation.current;
    const started = performance.now();
    setState((old) => ({ ...initial, loading: true, page: recommendationId ? old.page : null, expiresAt: recommendationId ? old.expiresAt : null }));
    try {
      const result = recommendationId
        ? await getIntelligenceSuggestion({ credential: secret, recommendationId, signal: controller.signal })
        : await getIntelligenceSuggestions({ credential: secret, selection: mode, offset, view, signal: controller.signal });
      if (version !== generation.current) return;
      const expiresAt = deadline(recommendationId ? [result] : result.items, started);
      if (expiresAt !== null && expiresAt <= performance.now()) throw new Error("A suggestion expired during the read. Refresh AI suggestions.");
      setState((old) => ({ ...old, loading: false, error: null,
        [recommendationId ? "detail" : "page"]: result,
        expiresAt: recommendationId && old.expiresAt !== null ? Math.min(old.expiresAt, expiresAt ?? Infinity) : expiresAt,
      }));
    } catch (error) {
      if (version !== generation.current) return;
      if (error.status === 401 || error.status === 403) setCredential("");
      setState({ ...initial, error: error.message });
    }
  }

  function connect(event) {
    event.preventDefault();
    const secret = input.current.value;
    input.current.value = "";
    setCredential(secret);
    load({ secret });
  }

  const tableColumns = [...columns, {
    header: "Evidence",
    render: (item) => <button type="button" onClick={() => load({ recommendationId: item.suggestion.recommendation_id })} disabled={state.loading}>View suggestion evidence</button>,
  }];

  return (
    <section className="ai-forecast-panel" aria-labelledby="ai-suggestion-heading">
      <p className="eyebrow">RetailOps AI · human review</p>
      <h2 id="ai-suggestion-heading">AI suggestions</h2>
      <p>Read proposed actions, rationale and evidence within your assigned suggestion scope. Human review is required; execution is not authorized.</p>
      {!credential ? (
        <form onSubmit={connect}>
          <label htmlFor="ai-suggestion-credential">Personal suggestion read credential</label>
          <input ref={input} id="ai-suggestion-credential" type="password" autoComplete="off" minLength={32} maxLength={256} required />
          <button type="submit" disabled={state.loading}>Connect AI suggestions</button>
          <p>Your credential stays in this tab's memory for up to five minutes and is cleared when the tab is hidden or the demo user changes.</p>
        </form>
      ) : (
        <div className="ai-forecast-controls">
          <label htmlFor="ai-suggestion-selection">Suggestion view</label>
          <select id="ai-suggestion-selection" value={selection} onChange={(event) => {
            setSelection(event.target.value);
            load({ mode: event.target.value });
          }}>
            <option value="current">Current suggestions</option>
            <option value="immutable_history">Immutable history</option>
          </select>
          <button type="button" onClick={() => load()} disabled={state.loading}>Refresh AI suggestions</button>
          <button type="button" onClick={clear}>Disconnect AI suggestions</button>
        </div>
      )}
      {state.loading && <p aria-live="polite">Reading AI suggestions…</p>}
      {state.error && <p role="alert">{state.error}</p>}
      {state.page && (
        <>
          <p>{state.page.selection === "current" ? "Valid at read time within the original upstream lifetime." : "Historical suggestions retain their original payload. Expired or future publications require a fresh review."} Source: retailops-ai. Every suggestion requires human review.</p>
          <DataTable title="AI suggestion results" columns={tableColumns} rows={state.page.items}
            getRowKey={(item) => item.suggestion.recommendation_id}
            emptyMessage="No AI suggestions are available in your assigned scope for this selection." />
          <p>Showing {state.page.items.length} of {state.page.pagination.total} scoped suggestions.</p>
          {state.page.pagination.offset > 0 && <button type="button" onClick={() => load()} disabled={state.loading}>First suggestion page</button>}
          {state.page.pagination.next_offset !== null && <button type="button" onClick={() => load({ offset: state.page.pagination.next_offset, view: state.page.view_sha256 })} disabled={state.loading}>Next suggestion page</button>}
        </>
      )}
      {state.detail && <Evidence item={state.detail} />}
    </section>
  );
}
