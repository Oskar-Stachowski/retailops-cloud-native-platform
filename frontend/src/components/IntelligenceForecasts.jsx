import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeDemoUserChanged } from "../auth/demoUser.js";
import { getIntelligenceForecast, getIntelligenceForecasts } from "../services/intelligenceApi.js";
import DataTable from "./DataTable.jsx";
import StatusBadge from "./StatusBadge.jsx";
import "../styles/intelligence-forecasts.css";

const initial = { loading: false, error: null, page: null, detail: null };
const value = (number) => number === null || number === undefined ? "Unavailable" : String(number);
const columns = [
  { header: "Product", accessor: (item) => item.forecast.product_id },
  { header: "Selling location / channel", accessor: (item) => `${item.forecast.selling_location_id} / ${item.forecast.channel}` },
  { header: "Origin (UTC)", accessor: (item) => item.forecast.forecast_origin },
  { header: "Target date / day", accessor: (item) => `${item.forecast.target_date} / ${item.forecast.horizon_days}` },
  { header: "Candidate mean (units)", accessor: (item) => value(item.forecast.prediction.candidate.mean) },
  { header: "Reference median (units)", accessor: (item) => value(item.forecast.prediction.baseline.median) },
  { header: "Freshness", render: (item) => <span><StatusBadge status={item.freshness.status} /> {item.freshness.reason}</span> },
];

function Lineage({ item }) {
  const forecast = item.forecast;
  const interval = forecast.prediction.baseline.interval;
  return (
    <section className="ai-forecast-lineage" aria-label="Forecast lineage">
      <h3>Forecast lineage</h3>
      <dl>
        {[
          ["Result", forecast.prediction_id], ["Source", item.source],
          ["Model", `${forecast.model_name} / ${forecast.model_version}`],
          ["Release", forecast.release_id], ["Inference run", forecast.inference_run_id],
          ["Prediction dataset", forecast.prediction_dataset_id], ["Source dataset", forecast.source_dataset_id],
          ["Curated dataset", forecast.curated_dataset_id], ["Feature set", forecast.feature_set_id],
          ["Computation receipt", forecast.receipt_id], ["Approval checksum", forecast.approval_sha256],
          ["Runtime checksum", forecast.runtime_pin_sha256], ["Image digest", forecast.image_digest],
          ["Generated (UTC)", forecast.generated_at], ["Received (UTC)", item.received_at],
          ["Quality at publication", forecast.quality_status], ["Approval valid until", forecast.approval_valid_until],
          ["Freshness", `${item.freshness.status}: ${item.freshness.reason}`],
          ["Freshness evaluated at", item.freshness.evaluated_at],
          ["Source watermark", forecast.freshness.source_watermark ?? "Unavailable"],
          ["Candidate mean source", forecast.prediction.metadata.mean_source],
          ["Reference recipe", forecast.prediction.metadata.recipe_id],
          ["Reference interval (units)", interval ? `${interval.lower} – ${interval.upper}` : "Unavailable"],
          ["Exclusion reason", forecast.prediction.exclusion_reason ?? "None"],
        ].map(([name, content]) => <div key={name}><dt>{name}</dt><dd>{content}</dd></div>)}
      </dl>
      <p>The interval is the model's reference interval. No confidence percentage or stockout probability is inferred.</p>
    </section>
  );
}

export default function IntelligenceForecasts() {
  const [credential, setCredential] = useState("");
  const [selection, setSelection] = useState("active");
  const [state, setState] = useState(initial);
  const input = useRef(null);
  const request = useRef(null);
  const generation = useRef(0);

  const clear = useCallback(() => {
    generation.current += 1;
    request.current?.abort();
    setCredential("");
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
    if (state.page?.selection !== "approved_release_as_of_run" || !state.page.heads?.length) return;
    const expiry = Math.min(...state.page.heads.map((head) => Date.parse(head.valid_until)));
    const timer = window.setTimeout(() => {
      generation.current += 1;
      request.current?.abort();
      setState({ ...initial, error: "The selected publication expired. Refresh AI forecasts." });
    }, Math.max(0, expiry - Date.now()));
    return () => window.clearTimeout(timer);
  }, [state.page]);

  async function load({ secret = credential, mode = selection, offset = 0, view = null, predictionId = null } = {}) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const version = ++generation.current;
    setState((old) => ({ ...old, loading: true, error: null, detail: null, page: predictionId ? old.page : null }));
    try {
      const result = predictionId
        ? await getIntelligenceForecast({ credential: secret, predictionId, signal: controller.signal })
        : await getIntelligenceForecasts({ credential: secret, selection: mode, offset, view, signal: controller.signal });
      if (version === generation.current) setState((old) => ({ ...old, loading: false, error: null, [predictionId ? "detail" : "page"]: result }));
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
    header: "Lineage",
    render: (item) => <button type="button" onClick={() => load({ predictionId: item.forecast.prediction_id })} disabled={state.loading}>View lineage</button>,
  }];

  return (
    <section className="ai-forecast-panel" aria-labelledby="ai-forecast-heading">
      <p className="eyebrow">RetailOps AI · daily forecast</p>
      <h2 id="ai-forecast-heading">AI forecasts</h2>
      <p>Daily observed sales units per product, selling location and channel. Access is limited to your assigned AI read scope.</p>
      {!credential ? (
        <form onSubmit={connect}>
          <label htmlFor="ai-read-credential">Personal AI read credential</label>
          <input ref={input} id="ai-read-credential" type="password" autoComplete="off" minLength={32} maxLength={256} required />
          <button type="submit" disabled={state.loading}>Connect AI forecasts</button>
          <p>Your credential stays in this tab's memory for up to five minutes and is cleared when the tab is hidden or the demo user changes.</p>
        </form>
      ) : (
        <div className="ai-forecast-controls">
          <label htmlFor="ai-forecast-selection">Publication view</label>
          <select id="ai-forecast-selection" value={selection} onChange={(event) => {
            setSelection(event.target.value);
            load({ mode: event.target.value });
          }}>
            <option value="active">Operator-selected publication</option>
            <option value="history">Immutable history</option>
          </select>
          <button type="button" onClick={() => load()} disabled={state.loading}>Refresh AI forecasts</button>
          <button type="button" onClick={clear}>Disconnect AI forecasts</button>
        </div>
      )}
      {state.loading && <p aria-live="polite">Reading AI forecasts…</p>}
      {state.error && <p role="alert">{state.error}</p>}
      {state.page && (
        <>
          <p>{selection === "active" ? "Selected by a private operator review with a limited validity window." : "Historical publications. These rows do not imply current approval."} Source: retailops-ai. Freshness is evaluated separately for every result.</p>
          <DataTable title="Daily AI forecast results" columns={tableColumns} rows={state.page.items}
            getRowKey={(item) => item.forecast.prediction_id}
            emptyMessage="No AI forecasts are available in your assigned scope for this selection." />
          <p>Showing {state.page.items.length} of {state.page.pagination.total} scoped results.</p>
          {state.page.pagination.offset > 0 && <button type="button" onClick={() => load()} disabled={state.loading}>First AI page</button>}
          {state.page.pagination.next_offset !== null && <button type="button" onClick={() => load({ offset: state.page.pagination.next_offset, view: state.page.view_sha256 })} disabled={state.loading}>Next AI page</button>}
        </>
      )}
      {state.detail && <Lineage item={state.detail} />}
    </section>
  );
}
