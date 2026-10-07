import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeDemoUserChanged } from "../auth/demoUser.js";
import { getIntelligenceModel, getIntelligenceModels } from "../services/intelligenceModelsApi.js";
import DataTable from "./DataTable.jsx";
import StatusBadge from "./StatusBadge.jsx";
import "../styles/intelligence-forecasts.css";

const initial = { loading: false, error: null, page: null, detail: null };
const value = (number) => number === null || number === undefined ? "Unavailable" : String(number);

function Lineage({ item }) {
  const result = item.result;
  const source = result.lineage || result;
  const anomaly = item.event_type === "anomaly_detected";
  return <section className="ai-forecast-lineage" aria-label="Model result lineage">
    <h3>Model result lineage</h3>
    <dl>{[
      ["Result", item.result_id], ["Source", item.source],
      ["Model", `${anomaly ? result.detector_name : result.model_name} / ${anomaly ? result.detector_version : result.model_version}`],
      ["Release", result.release_id], ["Inference run", result.inference_run_id],
      ["Source dataset", source.source_dataset_id], ["Curated dataset", source.curated_dataset_id],
      ["Feature set", source.feature_set_id || result.qualified_anomaly_input_id],
      ["Full DQ replay", result.full_dq_replay_id ?? "Unavailable"],
      ["Upstream bundle", source.upstream_bundle_id ?? "Unavailable"],
      ["Threshold version", result.threshold_version],
      ["Calibrator", result.calibrator_version ?? "Not applicable"],
      ["As of (UTC)", result.as_of], ["Generated (UTC)", result.generated_at],
      ["Received (UTC)", item.received_at], ["Quality at publication", result.quality_status],
      ["Read freshness", `${item.freshness.status}: ${item.freshness.reason}`],
      ["Source watermark", source.source_watermark ?? "Unavailable"],
    ].map(([label, content]) => <div key={label}><dt>{label}</dt><dd>{content ?? "Unavailable"}</dd></div>)}</dl>
  </section>;
}

export default function IntelligenceModels({ kind }) {
  const anomaly = kind === "anomaly_detected";
  const title = anomaly ? "AI anomalies" : "AI stockout risks";
  const id = anomaly ? "ai-anomaly" : "ai-stockout";
  const [credential, setCredential] = useState("");
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
  async function load({ secret = credential, offset = 0, view = null, resultId = null } = {}) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const version = ++generation.current;
    setState((old) => ({ ...old, loading: true, error: null, detail: null, page: resultId ? old.page : null }));
    try {
      const result = resultId
        ? await getIntelligenceModel({ kind, credential: secret, resultId, signal: controller.signal })
        : await getIntelligenceModels({ kind, credential: secret, offset, view, signal: controller.signal });
      if (version === generation.current) setState((old) => ({ ...old, loading: false, [resultId ? "detail" : "page"]: result }));
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
  const columns = [
    { header: "Product", accessor: (item) => item.result.product_id },
    { header: anomaly ? "Selling location / channel / currency" : "Stock location", accessor: (item) => anomaly ? `${item.result.selling_location_id} / ${item.result.channel} / ${item.result.currency}` : item.result.stock_location_id },
    { header: "As of (UTC)", accessor: (item) => item.result.as_of },
    { header: "Status", accessor: (item) => item.result.status },
    { header: anomaly ? "Observed / expected units" : "Probability within 7 days", accessor: (item) => anomaly ? `${value(item.result.observed_units)} / ${value(item.result.expected_units)}` : item.result.probability === null ? "Unavailable" : `${(item.result.probability * 100).toFixed(2)}%` },
    { header: anomaly ? "Alert / severity" : "Risk band", accessor: (item) => anomaly ? `${value(item.result.alert)} / ${value(item.result.severity)}` : value(item.result.risk_band) },
    { header: "Freshness", render: (item) => <StatusBadge status={item.freshness.status} /> },
    { header: "Quality", accessor: (item) => item.result.quality_status === "mechanics_only" ? "Contract fixture" : item.result.quality_status },
    { header: "Lineage", render: (item) => <button type="button" disabled={state.loading} onClick={() => load({ resultId: item.result_id })}>View model lineage</button> },
  ];
  return <section className="ai-forecast-panel" aria-labelledby={`${id}-heading`}>
    <p className="eyebrow">RetailOps AI · {anomaly ? "anomaly detector" : "physical stockout model"}</p>
    <h2 id={`${id}-heading`}>{title}</h2>
    <p>{anomaly ? "Daily anomaly decisions per product, selling location, channel and currency." : "Seven-day model risk per product and physical stock location. Current stockout and unavailable predictions have separate statuses."}</p>
    {!credential ? <form onSubmit={connect}>
      <label htmlFor={`${id}-credential`}>Personal model read credential</label>
      <input ref={input} id={`${id}-credential`} type="password" autoComplete="off" minLength={32} maxLength={256} required />
      <button type="submit" disabled={state.loading}>Connect {title}</button>
      <p>Your credential stays in this tab for up to five minutes and is cleared when the tab is hidden or the demo user changes.</p>
    </form> : <div className="ai-forecast-controls">
      <button type="button" onClick={() => load()} disabled={state.loading}>Refresh {title}</button>
      <button type="button" onClick={clear}>Disconnect {title}</button>
    </div>}
    {state.loading && <p aria-live="polite">Reading {title}…</p>}
    {state.error && <p role="alert">{state.error}</p>}
    {state.page && <>
      <p>Historical model publications, newest business origin first. Source: retailops-ai. Review freshness and lineage before taking action.</p>
      <DataTable title={`${title} results`} columns={columns} rows={state.page.items} getRowKey={(item) => item.result_id} emptyMessage="No model results are available in your assigned scope." />
      <p>Showing {state.page.items.length} of {state.page.pagination.total} scoped results.</p>
      {state.page.pagination.offset > 0 && <button type="button" onClick={() => load()} disabled={state.loading}>First model page</button>}
      {state.page.pagination.next_offset !== null && <button type="button" onClick={() => load({ offset: state.page.pagination.next_offset, view: state.page.view_sha256 })} disabled={state.loading}>Next model page</button>}
    </>}
    {state.detail && <Lineage item={state.detail} />}
  </section>;
}
