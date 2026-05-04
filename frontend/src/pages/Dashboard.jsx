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

function formatNumber(value) {
  if (value === undefined || value === null || value === "") {
    return "—";
  }

  if (Number.isFinite(Number(value))) {
    return Number(value).toLocaleString();
  }

  return value;
}

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
  return firstPresent(row, ["sku", "product_sku", "product_id"]);
}

function statusWithDefault(row) {
  if (row.status || row.state) {
    return firstPresent(row, ["status", "state"]);
  }

  return row.source === "recommendation" ? "proposed" : "open";
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
          row.risk_status || row.stock_risk || row.inventory_risk || row.status,
        )}
      />
    ),
  },
  {
    header: "Stock",
    accessor: (row) =>
      formatNumber(
        row.stock_qty ?? row.current_stock ?? row.quantity_on_hand ?? row.stock,
      ),
  },
  {
    header: "Reason",
    accessor: (row) => row.reason || row.explanation || row.notes || "—",
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

const salesTrendColumns = [
  {
    header: "Period",
    accessor: (row) => firstPresent(row, ["period", "date", "sales_date", "bucket"]),
  },
  {
    header: "Revenue",
    accessor: (row) => formatNumber(firstPresent(row, ["revenue", "sales_amount", "total_sales"])),
  },
  {
    header: "Units",
    accessor: (row) => formatNumber(firstPresent(row, ["units", "quantity", "total_quantity"])),
  },
  {
    header: "Orders",
    accessor: (row) => formatNumber(firstPresent(row, ["orders", "order_count", "sales_count"])),
  },
];

const alertColumns = [
  {
    header: "Alert",
    accessor: signalLabel,
  },
  {
    header: "Severity",
    render: (row) => (
      <StatusBadge status={firstPresent(row, ["severity", "priority"], "unknown")} />
    ),
  },
  {
    header: "Status",
    render: (row) => (
      <StatusBadge status={statusWithDefault(row)} />
    ),
  },
  {
    header: "SKU / Product",
    accessor: productReference,
  },
];

const recommendationColumns = [
  {
    header: "Recommendation",
    accessor: signalLabel,
  },
  {
    header: "Impact",
    accessor: (row) =>
      firstPresent(
        row,
        ["impact", "expected_impact", "business_impact", "priority", "severity"],
        "Operational follow-up",
      ),
  },
  {
    header: "Status",
    render: (row) => (
      <StatusBadge status={statusWithDefault(row)} />
    ),
  },
  {
    header: "SKU / Product",
    accessor: productReference,
  },
];

const workItemColumns = [
  {
    header: "Work item",
    accessor: signalLabel,
  },
  {
    header: "Source",
    accessor: (row) => humanizeToken(row.source, "Operations"),
  },
  {
    header: "Priority",
    render: (row) => (
      <StatusBadge status={firstPresent(row, ["priority", "severity"], "normal")} />
    ),
  },
  {
    header: "Status",
    render: (row) => (
      <StatusBadge status={statusWithDefault(row)} />
    ),
  },
];

function SourceCard({ name, source }) {
  const safeSource = source || {
    ok: false,
    label: "unavailable",
    path: "not configured",
    message: "Frontend source was not configured.",
  };

  return (
    <article className="source-card">
      <strong>{name}</strong>
      <StatusBadge status={safeSource.ok ? "connected" : "unavailable"}>
        {safeSource.label}
      </StatusBadge>
      <code>{safeSource.path}</code>
      <p>{safeSource.message}</p>
    </article>
  );
}

function ExecutiveSummary({ summary, operationalVisibility, fetchedAt }) {
  return (
    <section className="api-page__section" aria-label="Executive summary">
      <header className="section-heading">
        <p className="eyebrow">Sprint 5 executive view</p>
        <h2>Business decision snapshot</h2>
        <p>
          This section translates backend signals into management-friendly
          indicators: catalog coverage, demand planning, inventory risk and
          open operational work.
        </p>
      </header>

      <section className="metrics-grid">
        <MetricCard
          label="Risky products"
          value={summary.riskyProducts}
          helper="Products requiring inventory attention"
          tone={summary.riskyProducts > 0 ? "risk" : "positive"}
        />
        <MetricCard
          label="Open alerts"
          value={summary.openAlerts}
          helper="Operational signals from dashboard API"
          tone={summary.openAlerts > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Recommendations"
          value={summary.recommendationCount}
          helper="Suggested actions available for review"
          tone="positive"
        />
        <MetricCard
          label="Open work items"
          value={summary.openWorkItems}
          helper="Pending operational backlog"
          tone={summary.openWorkItems > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Sales trend rows"
          value={summary.salesTrendRecords}
          helper="Backend trend points loaded"
        />
        <MetricCard
          label="Last refresh"
          value={formatDateTime(summary.lastRefreshAt || fetchedAt)}
          helper={operationalVisibility.status || "Live local API evidence"}
        />
      </section>
    </section>
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
    salesTrend,
    alerts,
    recommendations,
    openWorkItems,
    operationalVisibility,
    sourceStatus,
    fetchedAt,
  } = state.data;

  return (
    <main className="api-page">
      <header className="api-page__header">
        <p className="eyebrow">Sprint 5 · dashboard and operations view MVP</p>
        <h1>Retail operations dashboard</h1>
        <p>
          This view connects the business dashboard to live FastAPI endpoints:
          KPI summary, sales trend, alerts, recommendations, open work items,
          stock-risk summary, products and forecasts.
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
          label="Forecast records"
          value={summary.forecastRecords}
          helper="Demand planning coverage"
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
          helper="Operations backlog signal"
          tone={summary.openAlerts > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Recommendations"
          value={summary.recommendationCount}
          helper="Action guidance from dashboard API"
          tone="positive"
        />
      </section>

      <ExecutiveSummary
        summary={summary}
        operationalVisibility={operationalVisibility}
        fetchedAt={fetchedAt}
      />

      <section className="source-grid" aria-label="Backend source status">
        <SourceCard name="Health" source={sourceStatus.health} />
        <SourceCard name="Readiness" source={sourceStatus.readiness} />
        <SourceCard name="Dashboard summary" source={sourceStatus.dashboardSummary} />
        <SourceCard
          name="Operational visibility"
          source={sourceStatus.operationalVisibility}
        />
        <SourceCard name="Sales trend" source={sourceStatus.salesTrend} />
        <SourceCard name="Alerts" source={sourceStatus.alerts} />
        <SourceCard name="Recommendations" source={sourceStatus.recommendations} />
        <SourceCard name="Open work items" source={sourceStatus.openWorkItems} />
        <SourceCard
          name="Stock-risk summary"
          source={sourceStatus.stockRiskSummary}
        />
        <SourceCard name="Products" source={sourceStatus.products} />
        <SourceCard name="Forecasts" source={sourceStatus.forecasts} />
        <SourceCard name="Stock risks" source={sourceStatus.stockRisks} />
      </section>

      <DataTable
        title="Sales trend"
        description="Baseline sales trend evidence for management and commercial planning. In future sprints this can become a chart."
        columns={salesTrendColumns}
        rows={salesTrend.slice(0, 8)}
        emptyMessage="Sales trend endpoint returned no records. Check /dashboard/sales-trend."
      />

      <DataTable
        title="Operational alerts"
        description="Alerts summarize signals that may require inventory, operations or commercial action."
        columns={alertColumns}
        rows={alerts.slice(0, 8)}
        emptyMessage="Dashboard alerts endpoint returned no records. No fake alert rows are displayed."
      />

      <DataTable
        title="Top recommendations"
        description="Recommendations show proposed actions before full workflow approval is implemented."
        columns={recommendationColumns}
        rows={recommendations.slice(0, 8)}
        emptyMessage="Dashboard recommendations endpoint returned no records. No local recommendation mocks are displayed."
      />

      <DataTable
        title="Open work items"
        description="Open work items connect decision signals with operational follow-up."
        columns={workItemColumns}
        rows={openWorkItems.slice(0, 8)}
        emptyMessage="Open work items endpoint returned no records. Workflow actions remain future scope."
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
        description={
          `Latest frontend refresh: ${formatDateTime(fetchedAt)}. ` +
          `Backend data refresh: ${formatDateTime(summary.lastRefreshAt)}.`
        }
        columns={forecastColumns}
        rows={forecasts.slice(0, 8)}
        emptyMessage="Forecast endpoint returned no records. Check seed data and /forecasts API response."
      />

      <DataTable
        title="Products from backend"
        description="Product records remain visible as traceability evidence for dashboard metrics."
        columns={productColumns}
        rows={products.slice(0, 8)}
        emptyMessage="Products endpoint returned no records. Check seed data and /products API response."
      />
    </main>
  );
}
