import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
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
    return "risk";
  }

  return consumerStates.some((consumer) => consumer.running) ? "positive" : "warning";
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
    accessor: (row) => row.product_id || "-",
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
    return <LoadingState title="Loading live operations" />;
  }

  if (state.error && !state.data) {
    return <ErrorState message={state.error.message} onRetry={handleRefresh} />;
  }

  const data = state.data || {};
  const metrics = data.metrics || {};
  const statusCounts = data.event_status_counts || {};
  const freshness = data.freshness || {};
  const consumerStates = data.consumer_states || [];

  return (
    <main className="api-page live-operations-page">
      <header className="api-page__header live-operations-header">
        <div>
          <p className="eyebrow">Real-time analysis</p>
          <h1>Live operations</h1>
          <p>
            Real-time sales, event processing and stream health from the
            persisted live metrics read model.
          </p>
        </div>

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
      </header>

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
          helper={`${data.window_minutes || windowMinutes} minute window`}
          tone="positive"
        />
        <MetricCard
          label="Units sold"
          value={formatNumber(metrics.units_sold)}
          helper={`${formatNumber(metrics.sales_events)} sale events`}
        />
        <MetricCard
          label="Alerts"
          value={formatNumber(metrics.alerts_created)}
          helper={`${formatNumber(metrics.anomalies_detected)} anomalies detected`}
          tone={Number(metrics.alerts_created) > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Freshness"
          value={freshnessLabel(freshness)}
          helper={formatDateTime(freshness.latest_event_at)}
          tone={freshness.is_fresh ? "positive" : "warning"}
        />
        <MetricCard
          label="Failed events"
          value={formatNumber(statusCounts.failed_dead_lettered)}
          helper={`${formatNumber(statusCounts.processed)} processed`}
          tone={Number(statusCounts.failed_dead_lettered) > 0 ? "risk" : "positive"}
        />
        <MetricCard
          label="Consumers"
          value={formatNumber(consumerStates.length)}
          helper={`Last refresh ${formatDateTime(state.fetchedAt)}`}
          tone={consumerTone(consumerStates)}
        />
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
            {freshness.is_fresh ? "fresh" : "stale"}
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

      <DataTable
        title="Recent stream events"
        description="Latest persisted event records from the real-time event log."
        columns={eventColumns}
        rows={data.recent_events || []}
        getRowKey={(row) => row.id || row.event_id}
        emptyMessage="No stream events have been persisted yet."
      />

      <DataTable
        title="Live alerts"
        description="Alert-like events derived from alert and anomaly event types."
        columns={alertColumns}
        rows={data.alerts || []}
        getRowKey={(row) => row.id || row.event_id || `${row.title || row.event_type || "alert"}:${row.ingested_at || "na"}`}
        emptyMessage="No alert-like events are available in the live stream."
      />

      <DataTable
        title="Consumer state"
        description="Persisted state for API consumers processing real-time events."
        columns={consumerColumns}
        rows={consumerStates}
        getRowKey={(row) => row.id || row.consumer_name}
        emptyMessage="No consumer state has been persisted yet."
      />

      <DataTable
        title="Raw live metrics"
        description="Metric observations aggregated by the live operations endpoint."
        columns={metricColumns}
        rows={metricRows}
        getRowKey={(row) => row.metric_name}
        emptyMessage="No metric observations are available for the selected window."
      />
    </main>
  );
}
