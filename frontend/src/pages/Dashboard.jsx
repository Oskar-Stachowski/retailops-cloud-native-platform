import { useCallback, useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { getDashboardData, normalizeRiskStatus } from "../services/retailopsApi";
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

const productColumns = [
  {
    header: "SKU",
    accessor: (row) => row.sku || row.product_sku || row.id,
  },
  {
    header: "Name",
    accessor: (row) => row.name || row.product_name,
  },
  {
    header: "Category",
    accessor: "category",
  },
  {
    header: "Status",
    render: (row) => (
      <StatusBadge status={row.status}>{row.status || "unknown"}</StatusBadge>
    ),
  },
];

const riskColumns = [
  {
    header: "SKU",
    accessor: (row) => row.sku || row.product_sku || row.product_id,
  },
  {
    header: "Risk",
    render: (row) => (
      <StatusBadge
        status={normalizeRiskStatus(
          row.risk_status || row.stock_risk || row.status,
        )}
      />
    ),
  },
  {
    header: "Stock",
    accessor: (row) =>
      row.stock_qty || row.current_stock || row.quantity_on_hand,
  },
  {
    header: "Reason",
    accessor: (row) => row.reason || row.explanation || row.notes,
  },
];

const forecastColumns = [
  {
    header: "Product ID",
    accessor: (row) => row.product_id || row.sku || row.product_sku || "—",
  },
  {
    header: "Period",
    accessor: (row) => {
      const start = row.forecast_period_start || row.forecast_date || row.date;
      const end = row.forecast_period_end;

      if (start && end) {
        return `${start} → ${end}`;
      }

      return start || "—";
    },
  },
  {
    header: "Predicted qty",
    accessor: (row) => {
      const quantity =
        row.predicted_quantity ??
        row.forecast_qty ??
        row.forecast_quantity ??
        row.predicted_demand;

      const unit = row.unit_of_measure || "";

      return quantity === undefined || quantity === null
        ? "—"
        : `${quantity} ${unit}`.trim();
    },
  },
  {
    header: "Confidence",
    accessor: (row) =>
      row.confidence_level === undefined || row.confidence_level === null
        ? "—"
        : `${Math.round(row.confidence_level * 100)}%`,
  },
  {
    header: "Method",
    accessor: (row) => row.method || row.model_version || row.model_name || "baseline",
  },
];

function SourceCard({ name, source }) {
  return (
    <article className="source-card">
      <strong>{name}</strong>
      <StatusBadge status={source.ok ? "connected" : "unavailable"}>
        {source.label}
      </StatusBadge>
      <code>{source.path}</code>
      <p>{source.message}</p>
    </article>
  );
}

export default function Dashboard() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function loadInitialDashboard() {
      try {
        const data = await getDashboardData();

        if (isMounted) {
          setState({
            loading: false,
            error: null,
            data,
          });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            loading: false,
            error,
            data: null,
          });
        }
      }
    }

    loadInitialDashboard();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleRetry = useCallback(async () => {
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

  if (state.loading) {
    return <LoadingState title="Loading RetailOps dashboard" />;
  }

  if (state.error) {
    return <ErrorState message={state.error.message} onRetry={handleRetry} />;
  }

  const {
    summary,
    products,
    forecasts,
    stockRisks,
    sourceStatus,
    fetchedAt,
  } = state.data;

  return (
    <main className="api-page">
      <header className="api-page__header">
        <p className="eyebrow">Live backend integration</p>
        <h1>Retail operations dashboard</h1>
        <p>
          This view is connected to FastAPI endpoints. It uses real backend
          responses and only derives fallback metrics from live endpoint payloads
          when the dashboard summary endpoint is not available yet.
        </p>
      </header>

      <section className="metrics-grid" aria-label="Dashboard metrics">
        <MetricCard
          label="Products"
          value={summary.totalProducts}
          helper="From products API or dashboard summary"
          tone="positive"
        />
        <MetricCard
          label="Active products"
          value={summary.activeProducts}
          helper="Current catalog scope"
          tone="positive"
        />
        <MetricCard
          label="Forecast records"
          value={summary.forecastRecords}
          helper="Forecast API coverage"
        />
        <MetricCard
          label="Stockout risks"
          value={summary.stockoutRisks}
          helper="Inventory decision signal"
          tone="risk"
        />
        <MetricCard
          label="Overstock risks"
          value={summary.overstockRisks}
          helper="Working capital signal"
          tone="warning"
        />
        <MetricCard
          label="Open alerts"
          value={summary.openAlerts}
          helper="Workflow placeholder"
        />
      </section>

      <section className="source-grid" aria-label="Backend source status">
        <SourceCard name="Health" source={sourceStatus.health} />
        <SourceCard name="Readiness" source={sourceStatus.readiness} />
        <SourceCard
          name="Dashboard summary"
          source={sourceStatus.dashboardSummary}
        />
        <SourceCard name="Products" source={sourceStatus.products} />
        <SourceCard name="Forecasts" source={sourceStatus.forecasts} />
        <SourceCard name="Stock risks" source={sourceStatus.stockRisks} />
      </section>

      <DataTable
        title="Products from backend"
        description={
          `Latest frontend refresh: ${formatDateTime(fetchedAt)}. ` +
          `Backend data refresh: ${formatDateTime(summary.lastRefreshAt)}.`
        }
        columns={productColumns}
        rows={products.slice(0, 8)}
        emptyMessage="Products endpoint returned no records. Check seed data and /products API response."
      />

      <DataTable
        title="Stock risk signals"
        description="Inventory risk data supports Operations and Inventory Planner decisions."
        columns={riskColumns}
        rows={stockRisks.slice(0, 8)}
        emptyMessage="Stock risk endpoint is empty or not implemented yet. No mock risks are displayed."
      />

      <DataTable
        title="Forecast records"
        description="Forecast data supports inventory planning and ML readiness evidence."
        columns={forecastColumns}
        rows={forecasts.slice(0, 8)}
        emptyMessage="Forecast endpoint returned no records. Check seed data and /forecasts API response."
      />
    </main>
  );
}