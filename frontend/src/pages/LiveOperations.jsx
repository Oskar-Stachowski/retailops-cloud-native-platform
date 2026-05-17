import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import { getLiveOperations } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

const WINDOW_OPTIONS = [5, 15, 60];
const REFRESH_INTERVAL_MS = 15000;

function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatNumber(value, options = {}) {
  if (value === undefined || value === null || value === "") {
    return "-";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  return number.toLocaleString(undefined, options);
}

function freshnessLabel(freshness) {
  if (!freshness?.latest_event_at) {
    return "No events";
  }

  if (freshness.freshness_seconds === null || freshness.freshness_seconds === undefined) {
    return "Unknown";
  }

  if (freshness.freshness_seconds < 60) {
    return `${Math.round(freshness.freshness_seconds)}s`;
  }

  return `${Math.round(freshness.freshness_seconds / 60)}m`;
}

function consumerTone(consumerStates) {
  if (!consumerStates?.length) {
    return "warning";
  }

  if (consumerStates.some((consumer) => Number(consumer.failed_events) > 0)) {
    return "danger";
  }

  return consumerStates.some((consumer) => consumer.running) ? "success" : "warning";
}

function positiveNumber(value) {
  const number = Number(value);

  return Number.isFinite(number) && number > 0;
}

function hasMetricActivity(metrics = {}) {
  return [
    metrics.revenue,
    metrics.units_sold,
    metrics.sales_events,
    metrics.stock_events,
    metrics.alerts_created,
    metrics.anomalies_detected,
    metrics.replenishment_units,
  ].some(positiveNumber);
}

function liveOpsMode({ recentEvents, liveAlerts, metrics, statusCounts }) {
  const hasEvents =
    recentEvents.length > 0 ||
    liveAlerts.length > 0 ||
    positiveNumber(statusCounts.total) ||
    hasMetricActivity(metrics);

  if (!hasEvents) {
    return {
      badge: "idle",
      status: "warning",
      title: "Idle local stream",
      description:
        "No stream events are present in the selected time window. " +
        "The UI is connected, but the local event pipeline has no recent traffic to display.",
    };
  }

  if (positiveNumber(statusCounts.failed_dead_lettered)) {
    return {
      badge: "attention",
      status: "error",
      title: "Stream needs attention",
      description:
        "Live events are flowing, but at least one event reached the failed/dead-lettered path.",
    };
  }

  return {
    badge: "active",
    status: "connected",
    title: "Active stream",
    description:
      "Recent live events are available in the persisted read model and can be inspected below.",
  };
}

const eventColumns = [
  {
    header: "Event",
    accessor: (row) => row.event_type || row.event_id,
  },
  {
    header: "Topic",
    accessor: (row) => row.topic || "-",
  },
  {
    header: "Status",
    render: (row) => <StatusBadge status={row.status || "unknown"} />,
  },
  {
    header: "Ingested",
    accessor: (row) => formatDateTime(row.ingested_at),
  },
  {
    header: "Error",
    accessor: (row) => row.error_message || "-",
  },
];

const alertColumns = [
  {
    header: "Signal",
    accessor: (row) => row.title || row.event_type || row.event_id,
  },
  {
    header: "Severity",
    render: (row) => <StatusBadge status={row.severity || "unknown"} />,
  },
  {
    header: "Product",
    render: (row) => <ProductReferenceCell row={row} />,
  },
  {
    header: "Ingested",
    accessor: (row) => formatDateTime(row.ingested_at),
  },
];

const consumerColumns = [
  {
    header: "Consumer",
    accessor: "consumer_name",
  },
  {
    header: "State",
    render: (row) => <StatusBadge status={row.running ? "connected" : "warning"} />,
  },
  {
    header: "Processed",
    accessor: (row) => formatNumber(row.processed_events),
  },
  {
    header: "Failed",
    accessor: (row) => formatNumber(row.failed_events),
  },
  {
    header: "Updated",
    accessor: (row) => formatDateTime(row.updated_at),
  },
];

const metricColumns = [
  {
    header: "Metric",
    accessor: (row) => row.metric_name,
  },
  {
    header: "Value",
    accessor: (row) => formatNumber(row.value, { maximumFractionDigits: 2 }),
  },
  {
    header: "Observations",
    accessor: (row) => formatNumber(row.observation_count),
  },
  {
    header: "Latest",
    accessor: (row) => formatDateTime(row.latest_observed_at),
  },
];

function rawMetricRows(rawMetrics = {}) {
  return Object.entries(rawMetrics).map(([metricName, metric]) => ({
    metric_name: metricName,
    ...metric,
  }));
}

export default function LiveOperations() {
  const [windowMinutes, setWindowMinutes] = useState(15);
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
    fetchedAt: null,
  });
  const activeRequestControllerRef = useRef(null);

  const loadLiveOperations = useCallback(async ({ showLoading = false } = {}) => {
    activeRequestControllerRef.current?.abort();

    const requestController = new AbortController();
    activeRequestControllerRef.current = requestController;

    if (showLoading) {
      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
    } else {
      setState((current) => ({
        ...current,
        error: null,
      }));
    }

    try {
      const data = await getLiveOperations({
        windowMinutes,
        recentEventsLimit: 20,
        alertsLimit: 10,
        signal: requestController.signal,
      });

      if (
        requestController.signal.aborted ||
        activeRequestControllerRef.current !== requestController
      ) {
        return;
      }

      setState({
        loading: false,
        error: null,
        data,
        fetchedAt: new Date().toISOString(),
      });
    } catch (error) {
      if (
        requestController.signal.aborted ||
        error?.code === "request_aborted" ||
        activeRequestControllerRef.current !== requestController
      ) {
        return;
      }

      setState((current) => ({
        ...current,
        loading: false,
        error,
      }));
    } finally {
      if (activeRequestControllerRef.current === requestController) {
        activeRequestControllerRef.current = null;
      }
    }
  }, [windowMinutes]);

  useEffect(() => {
    loadLiveOperations({ showLoading: true });
    const intervalId = window.setInterval(() => {
      loadLiveOperations();
    }, REFRESH_INTERVAL_MS);

    return () => {
      activeRequestControllerRef.current?.abort();
      activeRequestControllerRef.current = null;
      window.clearInterval(intervalId);
    };
  }, [loadLiveOperations]);

  const handleRefresh = useCallback(() => {
    loadLiveOperations({ showLoading: !state.data });
  }, [loadLiveOperations, state.data]);

  const metricRows = useMemo(
    () => rawMetricRows(state.data?.metrics?.raw_metrics),
    [state.data],
  );

  if (state.loading) {
    return (
      <main className="api-page live-operations-page">
        <LoadingState title="Loading live operations" />
      </main>
    );
  }

  if (state.error && !state.data) {
    return (
      <main className="api-page live-operations-page">
        <ErrorState message={state.error.message} onRetry={handleRefresh} />
      </main>
    );
  }

  const data = state.data || {};
  const metrics = data.metrics || {};
  const statusCounts = data.event_status_counts || {};
  const freshness = data.freshness || {};
  const consumerStates = data.consumer_states || [];
  const recentEvents = data.recent_events || [];
  const liveAlerts = data.alerts || [];
  const mode = liveOpsMode({ recentEvents, liveAlerts, metrics, statusCounts });
  const hasMetricRowsWithObservations = metricRows.some(
    (row) => positiveNumber(row.value) || positiveNumber(row.observation_count),
  );
  const hasVisibleLiveTables =
    recentEvents.length > 0 ||
    liveAlerts.length > 0 ||
    consumerStates.length > 0 ||
    hasMetricRowsWithObservations;
  const windowLabel = `${data.window_minutes || windowMinutes} minute window`;

  return (
    <main className="api-page live-operations-page">
      <PageHeader
        eyebrow="Real-time analysis"
        title="Live operations"
        description={
          "Real-time sales, event processing and stream health from the persisted live metrics " +
          "read model."
        }
        className="live-operations-header"
        actions={
          <div className="live-ops-controls" aria-label="Live operations controls">
            <label>
              Window
              <select
                value={windowMinutes}
                onChange={(event) => setWindowMinutes(Number(event.target.value))}
              >
                {WINDOW_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option} min
                  </option>
                ))}
              </select>
            </label>
            <button className="secondary-button" type="button" onClick={handleRefresh}>
              Refresh
            </button>
          </div>
        }
      />

      {state.error ? (
        <section className="state-card state-card--error">
          <div>
            <h2>Live refresh failed</h2>
            <p>{state.error.message}</p>
          </div>
          <button className="secondary-button" type="button" onClick={handleRefresh}>
            Retry
          </button>
        </section>
      ) : null}

      <section className="metrics-grid" aria-label="Live operations metrics">
        <MetricCard
          label="Revenue"
          value={formatNumber(metrics.revenue, { maximumFractionDigits: 2 })}
          helper={
            positiveNumber(metrics.revenue) ? windowLabel : "No sales revenue in selected window"
          }
          tone="neutral"
        />
        <MetricCard
          label="Units sold"
          value={formatNumber(metrics.units_sold)}
          helper={
            positiveNumber(metrics.sales_events)
              ? `${formatNumber(metrics.sales_events)} sale events`
              : "No sale events captured"
          }
          tone="neutral"
        />
        <MetricCard
          label="Alerts"
          value={formatNumber(metrics.alerts_created)}
          helper={
            positiveNumber(metrics.anomalies_detected)
              ? `${formatNumber(metrics.anomalies_detected)} anomalies detected`
              : "No anomaly events in selected window"
          }
          status={positiveNumber(metrics.alerts_created) ? "Watch" : "Clear"}
          tone={positiveNumber(metrics.alerts_created) ? "warning" : "success"}
        />
        <MetricCard
          label="Freshness"
          value={freshnessLabel(freshness)}
          helper={
            freshness.latest_event_at
              ? formatDateTime(freshness.latest_event_at)
              : "No event timestamp yet"
          }
          status={freshness.latest_event_at ? (freshness.is_fresh ? "Fresh" : "Stale") : "Idle"}
          tone={freshness.is_fresh ? "success" : "warning"}
        />
        <MetricCard
          label="Failed events"
          value={formatNumber(statusCounts.failed_dead_lettered)}
          helper={`${formatNumber(statusCounts.processed)} processed`}
          status={positiveNumber(statusCounts.failed_dead_lettered) ? "Error" : "OK"}
          tone={positiveNumber(statusCounts.failed_dead_lettered) ? "danger" : "success"}
        />
        <MetricCard
          label="Consumers"
          value={formatNumber(consumerStates.length)}
          helper={
            consumerStates.length > 0
              ? `Last refresh ${formatDateTime(state.fetchedAt)}`
              : "No consumer heartbeat recorded"
          }
          status={consumerStates.some((consumer) => consumer.running) ? "Running" : "Idle"}
          tone={consumerTone(consumerStates)}
        />
      </section>

      <section className={`live-ops-insight live-ops-insight--${mode.badge}`}>
        <header className="live-ops-insight__header">
          <div>
            <p className="eyebrow">Stream operating mode</p>
            <h2>{mode.title}</h2>
            <p>{mode.description}</p>
          </div>
          <StatusBadge status={mode.status}>{mode.badge}</StatusBadge>
        </header>

        <div className="live-ops-insight__grid">
          <article>
            <span>Current scope</span>
            <strong>{windowLabel}</strong>
            <p>
              Showing persisted stream metrics, recent event records, alert-like events and consumer
              state for the selected local time window.
            </p>
          </article>
          <article>
            <span>Next action</span>
            <strong>
              {mode.badge === "idle" ? "Generate demo traffic" : "Monitor stream health"}
            </strong>
            <p>
              {mode.badge === "idle"
                ? "Run the local demo traffic script or switch to a wider window, then refresh this view."
                : "Review failed events, alert-like records and consumer state before " +
                  "promoting the pipeline."}
            </p>
            {mode.badge === "idle" ? <code>scripts/dev/observability_demo_traffic.sh</code> : null}
          </article>
          <article>
            <span>Evidence</span>
            <strong>Backend read model connected</strong>
            <p>Last refresh: {formatDateTime(state.fetchedAt)}</p>
          </article>
        </div>
      </section>

      <section className="live-ops-status-grid" aria-label="Stream processing status">
        <article className="state-card live-ops-status-card">
          <div>
            <h2>Stream status</h2>
            <p>
              {formatNumber(statusCounts.total)} events in window /{" "}
              {formatNumber(statusCounts.ignored_duplicate)} duplicates ignored
            </p>
          </div>
          <StatusBadge status={freshness.is_fresh ? "connected" : "warning"}>
            {freshness.latest_event_at ? (freshness.is_fresh ? "fresh" : "stale") : "idle"}
          </StatusBadge>
        </article>
        <article className="state-card live-ops-status-card">
          <div>
            <h2>Inventory flow</h2>
            <p>
              {formatNumber(metrics.stock_events)} stock events /{" "}
              {formatNumber(metrics.replenishment_units)} replenished units
            </p>
          </div>
          <StatusBadge status={Number(metrics.stock_events) > 0 ? "connected" : "unknown"} />
        </article>
      </section>

      {hasVisibleLiveTables ? (
        <section className="live-ops-table-stack" aria-label="Live operations evidence tables">
          {recentEvents.length > 0 ? (
            <DataTable
              title="Recent stream events"
              description="Latest persisted event records from the real-time event log."
              columns={eventColumns}
              rows={recentEvents}
              getRowKey={(row) => row.id || row.event_id}
            />
          ) : null}

          {liveAlerts.length > 0 ? (
            <DataTable
              title="Live alerts"
              description="Alert-like events derived from alert and anomaly event types."
              columns={alertColumns}
              rows={liveAlerts}
              getRowKey={(row) =>
                row.id ||
                row.event_id ||
                `${row.title || row.event_type || "alert"}:${row.ingested_at || "na"}`
              }
            />
          ) : null}

          {consumerStates.length > 0 ? (
            <DataTable
              title="Consumer state"
              description="Persisted state for API consumers processing real-time events."
              columns={consumerColumns}
              rows={consumerStates}
              getRowKey={(row) => row.id || row.consumer_name}
            />
          ) : null}

          {hasMetricRowsWithObservations ? (
            <DataTable
              title="Raw live metrics"
              description="Metric observations aggregated by the live operations endpoint."
              columns={metricColumns}
              rows={metricRows}
              getRowKey={(row) => row.metric_name}
            />
          ) : null}
        </section>
      ) : (
        <section className="state-card state-card--empty live-ops-empty-state">
          <div>
            <p className="eyebrow">Controlled empty state</p>
            <h2>No stream events in the selected {windowMinutes}-minute window</h2>
            <p>
              This is a valid local-development state, not a frontend failure. Run the local event
              generator, widen the window to 60 minutes, then refresh to inspect persisted live
              metrics.
            </p>
          </div>
          <code>scripts/dev/observability_demo_traffic.sh</code>
        </section>
      )}
    </main>
  );
}
