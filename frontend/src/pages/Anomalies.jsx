import { useCallback, useEffect, useMemo, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import FeatureBoundary from "../components/FeatureBoundary";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import { getDashboardData, normalizeRiskStatus } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

function firstPresent(row, keys, fallback = "—") {
  for (const key of keys) {
    const value = row?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return fallback;
}

function humanizeToken(value, fallback = "—") {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function signalLabel(row) {
  const explicitLabel = firstPresent(
    row,
    ["title", "message", "name", "description", "recommendation", "action"],
    "",
  );

  if (explicitLabel) {
    return explicitLabel;
  }

  const type = humanizeToken(row.type, "Operational signal");
  const source = humanizeToken(row.source, "");

  return source ? `${type} (${source})` : type;
}

function productReference(row) {
  return <ProductReferenceCell row={row} />;
}

function statusWithDefault(row) {
  if (row.status || row.state) {
    return firstPresent(row, ["status", "state"]);
  }

  return "open";
}

function buildAnomalySignalRows(alerts = [], stockRisks = []) {
  const alertRows = alerts.map((row, index) => ({
    ...row,
    id: row.id || row.alert_id || `alert-${index}`,
    signal: signalLabel(row),
    source: "Dashboard alerts",
    severity: firstPresent(row, ["severity", "priority"], "unknown"),
    status: statusWithDefault(row),
    product: productReference(row),
  }));

  const riskRows = stockRisks.map((row, index) => ({
    ...row,
    id: row.id || row.product_id || row.sku || `stock-risk-${index}`,
    signal: firstPresent(row, ["reason", "explanation", "notes"], "Inventory risk signal"),
    source: "Stock-risk summary",
    severity: normalizeRiskStatus(
      row.risk_status || row.stock_risk || row.inventory_risk || row.status,
    ),
    status: statusWithDefault(row),
    product: productReference(row),
  }));

  return [...alertRows, ...riskRows];
}

const anomalySignalColumns = [
  {
    header: "Signal",
    accessor: "signal",
  },
  {
    header: "Source",
    accessor: "source",
  },
  {
    header: "Severity / risk",
    render: (row) => <StatusBadge status={row.severity}>{row.severity}</StatusBadge>,
  },
  {
    header: "Status",
    render: (row) => <StatusBadge status={row.status}>{row.status}</StatusBadge>,
  },
  {
    header: "SKU / Product",
    render: productReference,
  },
];

export default function Anomalies() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  const loadAnomalyContext = useCallback(async () => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const data = await getDashboardData();

      setState({
        loading: false,
        error: null,
        data,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        data: null,
      });
    }
  }, []);

  useEffect(() => {
    let isCurrent = true;

    getDashboardData()
      .then((data) => {
        if (!isCurrent) {
          return;
        }

        setState({
          loading: false,
          error: null,
          data,
        });
      })
      .catch((error) => {
        if (!isCurrent) {
          return;
        }

        setState({
          loading: false,
          error,
          data: null,
        });
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  const anomalyRows = useMemo(
    () => buildAnomalySignalRows(state.data?.alerts, state.data?.stockRisks),
    [state.data?.alerts, state.data?.stockRisks],
  );

  if (state.loading) {
    return (
      <main className="api-page">
        <LoadingState title="Loading anomaly context" />
      </main>
    );
  }

  if (state.error) {
    return (
      <main className="api-page">
        <PageHeader
          eyebrow="Anomaly monitoring"
          title="Anomalies"
          description="Current release exposes anomaly-adjacent signals through the dashboard endpoints while the dedicated anomaly queue remains planned scope."
        />
        <ErrorState message={state.error.message} onRetry={loadAnomalyContext} />
      </main>
    );
  }

  const summary = state.data?.summary || {};
  const alerts = state.data?.alerts || [];
  const stockRisks = state.data?.stockRisks || [];

  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Anomaly monitoring"
        title="Anomalies"
        description="Operational anomaly context built from real dashboard alerts and stock-risk signals. The dedicated anomaly queue is shown as a planned boundary, not as missing functionality."
      />

      <section className="metrics-grid" aria-label="Anomaly context metrics">
        <MetricCard
          label="Alert signals"
          value={alerts.length || summary.openAlerts || 0}
          helper="Loaded from dashboard alerts"
          tone={alerts.length ? "warning" : "positive"}
        />
        <MetricCard
          label="Stock-risk signals"
          value={stockRisks.length || summary.stockoutRisks || 0}
          helper="Inventory anomalies visible today"
          tone={stockRisks.length ? "risk" : "positive"}
        />
        <MetricCard
          label="Open work items"
          value={summary.openWorkItems || 0}
          helper="Follow-up backlog from dashboard"
          tone={summary.openWorkItems > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Dedicated queue"
          value="Planned"
          helper="Future anomaly workflow route"
        />
      </section>

      <FeatureBoundary
        eyebrow="Release boundary"
        title="Current release exposes anomaly signals through operational views"
        currentScope="Dedicated anomaly investigation is planned as a future extension. Current release already surfaces anomaly-adjacent signals through Dashboard, stock-risk summary and Product 360 workflows."
        availableSignals={[
          "Dashboard alerts from the live FastAPI dashboard endpoint",
          "Stockout and overstock risk signals from inventory risk summaries",
          "Open work items that can become investigation tasks",
        ]}
        futureScope="Add a dedicated /anomalies endpoint with investigation status, owner assignment, filtering and audit trail."
        plannedSteps={[
          "Add anomaly records and investigation workflow in the API",
          "Connect filters by SKU, severity, anomaly type and status",
          "Promote selected signals into Product 360 and Action Queue follow-up",
        ]}
      />

      <DataTable
        title="Available anomaly-related signals"
        description="This table uses existing backend-backed dashboard and stock-risk data instead of fake anomaly rows."
        columns={anomalySignalColumns}
        rows={anomalyRows.slice(0, 10)}
        getRowKey={(row) => row.id}
        emptyMessage="No anomaly-adjacent signals were returned by the current dashboard endpoints. Dedicated anomaly records remain planned scope."
      />
    </main>
  );
}
