import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { getProduct360 } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatDateRange(start, end) {
  if (!start && !end) {
    return "—";
  }

  return `${start || "—"} → ${end || "—"}`;
}

function formatCurrency(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${Math.round(Number(value) * 100)}%`;
}

function formatTitle(value) {
  if (!value) {
    return "—";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const salesColumns = [
  { header: "Sold at", accessor: (row) => formatDateTime(row.sold_at) },
  { header: "Quantity", accessor: "quantity" },
  { header: "Channel", accessor: (row) => row.channel || "—" },
  { header: "Revenue", accessor: (row) => formatCurrency(row.total_amount) },
];

const inventoryColumns = [
  { header: "Recorded", accessor: (row) => formatDateTime(row.recorded_at) },
  { header: "Stock", accessor: (row) => `${row.stock_quantity} ${row.unit_of_measure}` },
  { header: "Warehouse", accessor: "warehouse_code" },
];

const forecastColumns = [
  {
    header: "Period",
    accessor: (row) => formatDateRange(row.forecast_period_start, row.forecast_period_end),
  },
  {
    header: "Predicted",
    accessor: (row) => `${row.predicted_quantity} ${row.unit_of_measure}`,
  },
  { header: "Confidence", accessor: (row) => formatPercent(row.confidence_level) },
  { header: "Method", accessor: "method" },
];

const anomalyColumns = [
  { header: "Type", accessor: (row) => formatTitle(row.anomaly_type) },
  { header: "Metric", accessor: "metric_name" },
  {
    header: "Severity",
    render: (row) => <StatusBadge status={row.severity}>{row.severity}</StatusBadge>,
  },
  { header: "Deviation", accessor: (row) => `${row.deviation_percent}%` },
  { header: "Detected", accessor: (row) => formatDateTime(row.detected_at) },
];

const alertColumns = [
  { header: "Alert", accessor: "title" },
  {
    header: "Severity",
    render: (row) => <StatusBadge status={row.severity}>{row.severity}</StatusBadge>,
  },
  {
    header: "Status",
    render: (row) => <StatusBadge status={row.status}>{row.status}</StatusBadge>,
  },
  { header: "Action", accessor: "recommended_action" },
];

const recommendationColumns = [
  { header: "Recommendation", accessor: "recommended_action" },
  { header: "Type", accessor: (row) => formatTitle(row.recommendation_type) },
  {
    header: "Status",
    render: (row) => <StatusBadge status={row.status}>{row.status}</StatusBadge>,
  },
  { header: "Generated", accessor: (row) => formatDateTime(row.generated_at) },
];

const workflowColumns = [
  { header: "Action", accessor: (row) => formatTitle(row.action_type) },
  { header: "Alert", accessor: (row) => row.alert_title || "—" },
  { header: "User", accessor: (row) => row.performed_by_login || "—" },
  {
    header: "Status change",
    accessor: (row) => `${row.previous_status || "—"} → ${row.new_status || "—"}`,
  },
  { header: "Performed", accessor: (row) => formatDateTime(row.performed_at) },
];

export default function Product360() {
  const { productId } = useParams();
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
    productId: null,
  });

  const handleRetry = useCallback(async () => {
    setState({
      loading: true,
      error: null,
      data: null,
      productId,
    });

    try {
      const data = await getProduct360(productId);

      setState({
        loading: false,
        error: null,
        data,
        productId,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        data: null,
        productId,
      });
    }
  }, [productId]);

  useEffect(() => {
    let isCurrent = true;

    async function loadInitialProduct360() {
      try {
        const data = await getProduct360(productId);

        if (isCurrent) {
          setState({
            loading: false,
            error: null,
            data,
            productId,
          });
        }
      } catch (error) {
        if (isCurrent) {
          setState({
            loading: false,
            error,
            data: null,
            productId,
          });
        }
      }
    }

    loadInitialProduct360();

    return () => {
      isCurrent = false;
    };
  }, [productId]);

  const isLoading = state.loading || state.productId !== productId;

  if (isLoading) {
    return <LoadingState title="Loading Product 360" />;
  }

  if (state.error) {
    return <ErrorState message={state.error.message} onRetry={handleRetry} />;
  }

  if (!state.data) {
    return <ErrorState message="Product 360 data is not available." onRetry={handleRetry} />;
  }

  const { product, metrics, stock_risk: stockRisk } = state.data;

  return (
    <main className="api-page product-360-page">
      <header className="api-page__header product-360-header">
        <Link className="inline-link" to="/products">← Back to products</Link>
        <p className="eyebrow">Sprint 6 · Product 360</p>
        <h1>{product.name}</h1>
        <p>
          SKU {product.sku} · {product.category || "No category"} · {product.brand || "No brand"}
        </p>
        <StatusBadge status={product.status}>{product.status}</StatusBadge>
      </header>

      <section className="metrics-grid">
        <MetricCard label="Risk status" value={formatTitle(metrics.risk_status)} helper="From stock risk model" tone="warning" />
        <MetricCard label="Current stock" value={metrics.current_stock ?? "—"} helper="Latest inventory snapshot" />
        <MetricCard label="Forecast qty" value={metrics.latest_forecast_quantity ?? "—"} helper="Latest demand signal" />
        <MetricCard label="Revenue" value={formatCurrency(metrics.total_revenue)} helper="Sales evidence" tone="positive" />
        <MetricCard label="Open alerts" value={metrics.open_alert_count} helper="Operational backlog" tone="warning" />
        <MetricCard label="Recommendations" value={metrics.open_recommendation_count} helper="Proposed actions" tone="positive" />
      </section>

      <section className="feature-boundary">
        <h2>Operational workflow boundary</h2>
        <p>
          This Sprint 6 view reads workflow context, but it does not mutate workflow state yet.
          Approve, reject, assign and comment actions remain future backend write APIs.
        </p>
      </section>

      <DataTable
        title="Stock risk"
        description="Single product stock-risk context used by inventory planners."
        columns={[
          { header: "SKU", accessor: "sku" },
          { header: "Current stock", accessor: "current_stock" },
          { header: "Forecast", accessor: "forecast_quantity" },
          {
            header: "Risk",
            render: (row) => <StatusBadge status={row.risk_status}>{formatTitle(row.risk_status)}</StatusBadge>,
          },
        ]}
        rows={stockRisk ? [stockRisk] : []}
        emptyMessage="No stock-risk row is available for this product yet."
      />

      <DataTable
        title="Recent sales"
        description="Sales evidence behind Product 360 commercial context."
        columns={salesColumns}
        rows={state.data.sales}
        emptyMessage="No sales records returned for this product."
      />

      <DataTable
        title="Inventory snapshots"
        description="Latest inventory evidence used for stock-risk decisions."
        columns={inventoryColumns}
        rows={state.data.inventory_snapshots}
        emptyMessage="No inventory snapshots returned for this product."
      />

      <DataTable
        title="Forecast records"
        description="Demand-planning records linked to the product."
        columns={forecastColumns}
        rows={state.data.forecasts}
        emptyMessage="No forecasts returned for this product."
      />

      <DataTable
        title="Anomalies"
        description="Product-level anomaly signals from operational data."
        columns={anomalyColumns}
        rows={state.data.anomalies}
        emptyMessage="No anomalies returned for this product."
      />

      <DataTable
        title="Alerts"
        description="Operational alerts that can later drive workflow actions."
        columns={alertColumns}
        rows={state.data.alerts}
        emptyMessage="No alerts returned for this product."
      />

      <DataTable
        title="Recommendations"
        description="Proposed actions before full workflow approval is implemented."
        columns={recommendationColumns}
        rows={state.data.recommendations}
        emptyMessage="No recommendations returned for this product."
      />

      <DataTable
        title="Workflow actions"
        description="Audit trail linked through product alerts."
        columns={workflowColumns}
        rows={state.data.workflow_actions}
        emptyMessage="No workflow actions returned for this product."
      />
    </main>
  );
}
