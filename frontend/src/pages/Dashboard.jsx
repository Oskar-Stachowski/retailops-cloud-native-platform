import { useCallback, useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import {
  DistributionBars,
  InsightVisualCard,
  LineSparkChart,
  MiniBarList,
} from "../components/MiniVisualizations";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
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

function numberValue(value) {
  const parsedValue = Number(value);

  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function firstNumeric(row, keys, fallback = null) {
  for (const key of keys) {
    const value = numberValue(row?.[key]);

    if (value !== null) {
      return value;
    }
  }

  return fallback;
}

function countByLabel(rows, accessor, fallbackLabel = "Unknown") {
  const counts = new Map();

  for (const row of rows || []) {
    const rawLabel = accessor(row);
    const label = humanizeToken(rawLabel, fallbackLabel);

    counts.set(label, (counts.get(label) || 0) + 1);
  }

  return Array.from(counts, ([label, value]) => ({ label, value })).sort(
    (left, right) => right.value - left.value || left.label.localeCompare(right.label),
  );
}

function salesTrendValue(row) {
  return firstNumeric(
    row,
    ["revenue", "sales_amount", "total_sales", "units", "quantity", "total_quantity", "orders", "order_count"],
    0,
  );
}

function salesTrendLabel(row, index) {
  return firstPresent(row, ["period", "date", "sales_date", "bucket"], `Point ${index + 1}`);
}

function stockRiskDistribution(rows, summary) {
  const distribution = countByLabel(
    rows,
    (row) => normalizeRiskStatus(
      row.risk_status || row.stock_risk || row.inventory_risk || row.status,
    ),
    "Normal",
  );

  if (distribution.length) {
    return distribution;
  }

  return [
    { label: "Stockout risk", value: summary.stockoutRisks },
    { label: "Overstock risk", value: summary.overstockRisks },
  ];
}

function forecastConfidenceItems(rows) {
  return (rows || []).slice(0, 6).map((row, index) => {
    const confidence = firstNumeric(row, ["confidence_level", "confidence", "confidence_score"], 0);
    const normalizedConfidence = confidence <= 1 ? confidence * 100 : confidence;
    const label = firstPresent(
      row,
      ["sku", "product_sku", "product_name", "product_id"],
      `Forecast ${index + 1}`,
    );

    return {
      label,
      value: Math.round(normalizedConfidence),
      valueLabel: `${Math.round(normalizedConfidence)}%`,
    };
  });
}

function workflowStatusDistribution(rows, alerts, recommendations) {
  const distribution = countByLabel(
    rows,
    (row) => row.status || row.state || row.workflow_status,
    "Open",
  );

  if (distribution.length) {
    return distribution;
  }

  return [
    { label: "Open alerts", value: alerts.length },
    { label: "Recommendations", value: recommendations.length },
  ];
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
  return <ProductReferenceCell row={row} />;
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
    header: "Product",
    render: productReference,
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

const SOURCE_DEFINITIONS = [
  ["health", "API health"],
  ["readiness", "Readiness"],
  ["dashboardSummary", "Dashboard summary"],
  ["operationalVisibility", "Operational visibility"],
  ["salesTrend", "Sales trend"],
  ["alerts", "Alerts"],
  ["recommendations", "Recommendations"],
  ["openWorkItems", "Open work items"],
  ["stockRiskSummary", "Stock-risk summary"],
  ["products", "Products"],
  ["forecasts", "Forecasts"],
  ["stockRisks", "Stock risks"],
];

function sourceEntries(sourceStatus) {
  return SOURCE_DEFINITIONS.map(([key, label]) => {
    const source = sourceStatus?.[key] || {};

    return {
      key,
      label,
      ok: Boolean(source.ok),
      statusLabel: source.label || (source.ok ? "connected" : "unavailable"),
      path: source.path || "not configured",
    };
  });
}

function DashboardSection({ eyebrow, title, description, children }) {
  return (
    <section className="dashboard-section">
      <header className="dashboard-section__header">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </header>
      {children}
    </section>
  );
}

function PortfolioEvidenceBanner({
  summary,
  operationalVisibility,
  sourceStatus,
  fetchedAt,
}) {
  const entries = sourceEntries(sourceStatus);
  const connectedCount = entries.filter((entry) => entry.ok).length;

  return (
    <section
      className="dashboard-evidence-banner"
      aria-label="Portfolio evidence summary"
    >
      <div className="dashboard-evidence-banner__copy">
        <p className="eyebrow">Portfolio entry point</p>
        <h2>Executive dashboard backed by live platform evidence</h2>
        <p>
          This screen starts with business KPIs, then shows operational signals,
          backend integration health and traceable records from the local FastAPI
          platform.
        </p>
      </div>

      <dl className="dashboard-evidence-banner__facts">
        <div>
          <dt>Backend sources</dt>
          <dd>
            {connectedCount}/{entries.length}
          </dd>
        </div>
        <div>
          <dt>Operational state</dt>
          <dd>{operationalVisibility.status || "Live API"}</dd>
        </div>
        <div>
          <dt>Latest refresh</dt>
          <dd>{formatDateTime(summary.lastRefreshAt || fetchedAt)}</dd>
        </div>
      </dl>
    </section>
  );
}

function BackendIntegrationPanel({ sourceStatus }) {
  const entries = sourceEntries(sourceStatus);
  const connectedCount = entries.filter((entry) => entry.ok).length;
  const allConnected = connectedCount === entries.length;

  return (
    <section
      className="backend-evidence-panel"
      aria-label="Backend integration status"
    >
      <header className="backend-evidence-panel__header">
        <div>
          <p className="eyebrow">Backend integration evidence</p>
          <h2>Live FastAPI source status</h2>
          <p>
            Compact endpoint evidence replaces a wall of status cards while still
            showing that dashboard data is coming from backend services.
          </p>
        </div>
        <div className="backend-evidence-panel__summary">
          <strong>
            {connectedCount}/{entries.length}
          </strong>
          <StatusBadge status={allConnected ? "connected" : "warning"}>
            {allConnected ? "Connected" : "Partial"}
          </StatusBadge>
        </div>
      </header>

      <ul className="backend-evidence-list">
        {entries.map((entry) => (
          <li key={entry.key} className="backend-evidence-list__item">
            <div>
              <strong>{entry.label}</strong>
              <code>{entry.path}</code>
            </div>
            <StatusBadge status={entry.ok ? "connected" : "unavailable"}>
              {entry.statusLabel}
            </StatusBadge>
          </li>
        ))}
      </ul>
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
    return (
      <main className="api-page">
        <LoadingState title="Loading RetailOps dashboard" />
      </main>
    );
  }

  if (state.error) {
    return (
      <main className="api-page">
        <ErrorState message={state.error.message} onRetry={handleRetry} />
      </main>
    );
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
      <PageHeader
        eyebrow="Operations command center"
        title="RetailOps executive dashboard"
        description="Portfolio entry point for the RetailOps platform: business KPIs first, operational signals second, and compact backend integration evidence behind the data."
      />

      <PortfolioEvidenceBanner
        summary={summary}
        operationalVisibility={operationalVisibility}
        sourceStatus={sourceStatus}
        fetchedAt={fetchedAt}
      />

      <DashboardSection
        eyebrow="Business KPIs"
        title="Commercial and inventory health"
        description="Top-level indicators for catalog coverage, demand planning, inventory risk and action guidance."
      >
        <section
          className="metrics-grid dashboard-kpi-grid"
          aria-label="Business KPI metrics"
        >
          <MetricCard
            label="Products"
            value={summary.totalProducts}
            helper="Catalog records available through the products API"
            tone="neutral"
          />
          <MetricCard
            label="Forecast coverage"
            value={summary.forecastRecords}
            helper="Demand planning records available for review"
            tone="neutral"
          />
          <MetricCard
            label="Stockout risks"
            value={summary.stockoutRisks}
            helper="Inventory decision signal"
            status="Risk"
            tone="danger"
          />
          <MetricCard
            label="Overstock risks"
            value={summary.overstockRisks}
            helper="Working capital signal"
            status="Watch"
            tone="warning"
          />
          <MetricCard
            label="Open alerts"
            value={summary.openAlerts}
            helper="Operations backlog signal"
            status={summary.openAlerts > 0 ? "Open" : "Clear"}
            tone={summary.openAlerts > 0 ? "warning" : "success"}
          />
          <MetricCard
            label="Recommendations"
            value={summary.recommendationCount}
            helper="Action guidance from dashboard API"
            tone="neutral"
          />
        </section>
      </DashboardSection>

      <DashboardSection
        eyebrow="Operational signals"
        title="Decision queue summary"
        description="Management-friendly indicators that connect backend signals with follow-up work."
      >
        <section
          className="metrics-grid dashboard-signal-grid"
          aria-label="Operational signal metrics"
        >
          <MetricCard
            label="Risky products"
            value={summary.riskyProducts}
            helper="Products requiring inventory attention"
            status={summary.riskyProducts > 0 ? "Risk" : "Clear"}
            tone={summary.riskyProducts > 0 ? "danger" : "success"}
          />
          <MetricCard
            label="Open work items"
            value={summary.openWorkItems}
            helper="Pending operational backlog"
            status={summary.openWorkItems > 0 ? "Backlog" : "Clear"}
            tone={summary.openWorkItems > 0 ? "warning" : "success"}
          />
          <MetricCard
            label="Sales trend rows"
            value={summary.salesTrendRecords}
            helper="Backend trend points loaded"
            tone="neutral"
          />
          <MetricCard
            label="Last refresh"
            value={formatDateTime(summary.lastRefreshAt || fetchedAt)}
            helper={operationalVisibility.status || "Live local API evidence"}
            tone="neutral"
          />
        </section>
      </DashboardSection>

      <BackendIntegrationPanel sourceStatus={sourceStatus} />


      <DashboardSection
        eyebrow="Visual insights"
        title="Mini visualizations for portfolio review"
        description="Small charts make the dashboard less table-heavy while keeping the data source simple and traceable."
      >
        <section
          className="mini-visual-grid dashboard-visual-grid"
          aria-label="Dashboard mini visualizations"
        >
          <InsightVisualCard
            eyebrow="Sales trend"
            title="Revenue / volume movement"
            description="Thirty-day trend window from the sales trend endpoint."
          >
            <LineSparkChart
              rows={salesTrend}
              valueAccessor={salesTrendValue}
              labelAccessor={salesTrendLabel}
              emptyMessage="Sales trend endpoint returned no chartable values."
            />
          </InsightVisualCard>

          <InsightVisualCard
            eyebrow="Stock risk"
            title="Inventory risk distribution"
            description="Risk mix across stockout, overstock and normal inventory signals."
          >
            <DistributionBars
              items={stockRiskDistribution(stockRisks, summary)}
              emptyMessage="No stock risk distribution available."
            />
          </InsightVisualCard>

          <InsightVisualCard
            eyebrow="Forecasts"
            title="Confidence mini bars"
            description="Quick confidence scan across the latest forecast records."
          >
            <MiniBarList
              items={forecastConfidenceItems(forecasts)}
              emptyMessage="Forecast rows do not expose confidence values yet."
            />
          </InsightVisualCard>

          <InsightVisualCard
            eyebrow="Alerts"
            title="Open alerts by severity"
            description="Severity distribution from operational alert signals."
          >
            <DistributionBars
              items={countByLabel(alerts, (row) => row.severity || row.priority, "Unknown")}
              emptyMessage="No alert severity data available."
            />
          </InsightVisualCard>

          <InsightVisualCard
            eyebrow="Workflow"
            title="Queue by status"
            description="Workflow backlog shape from open work items and decisions."
          >
            <DistributionBars
              items={workflowStatusDistribution(openWorkItems, alerts, recommendations)}
              emptyMessage="No workflow status distribution available."
            />
          </InsightVisualCard>

          <InsightVisualCard
            eyebrow="Catalog"
            title="Product category distribution"
            description="Category mix from backend product records."
          >
            <DistributionBars
              items={countByLabel(products, (row) => row.category, "Uncategorized")}
              emptyMessage="No product category data available."
            />
          </InsightVisualCard>
        </section>
      </DashboardSection>

      <DashboardSection
        eyebrow="Tables / evidence"
        title="Traceable records behind the dashboard"
        description="Business tables remain available below the executive summary for reviewers who want to inspect the underlying records."
      >
        <DataTable
          title="Sales trend"
          description="Baseline sales trend evidence for management and commercial planning. These rows also feed the mini line chart above."
          columns={salesTrendColumns}
          rows={salesTrend.slice(0, 8)}
          getRowKey={(row) =>
            row.id || row.period || row.date || row.sales_date || row.bucket
          }
          emptyMessage="Sales trend endpoint returned no records. Check /dashboard/sales-trend."
        />

        <DataTable
          title="Operational alerts"
          description="Alerts summarize signals that may require inventory, operations or commercial action."
          columns={alertColumns}
          rows={alerts.slice(0, 8)}
          getRowKey={(row) =>
            row.id ||
            row.alert_id ||
            `${row.title || row.message || "alert"}:${
              row.detected_at || row.created_at || "na"
            }`
          }
          emptyMessage="Dashboard alerts endpoint returned no records. No fake alert rows are displayed."
        />

        <DataTable
          title="Top recommendations"
          description="Recommendations show proposed actions before full workflow approval is implemented."
          columns={recommendationColumns}
          rows={recommendations.slice(0, 8)}
          getRowKey={(row) =>
            row.id ||
            row.recommendation_id ||
            `${row.title || row.recommended_action || "recommendation"}:${
              row.generated_at || row.created_at || "na"
            }`
          }
          emptyMessage="Dashboard recommendations endpoint returned no records. No local recommendation mocks are displayed."
        />

        <DataTable
          title="Open work items"
          description="Open work items connect decision signals with operational follow-up."
          columns={workItemColumns}
          rows={openWorkItems.slice(0, 8)}
          getRowKey={(row) =>
            row.id ||
            `${row.source || "work"}:${
              row.title || row.message || row.name || "item"
            }:${
              row.updated_at || row.created_at || "na"
            }`
          }
          emptyMessage="Open work items endpoint returned no records. Workflow actions remain future scope."
        />

        <DataTable
          title="Stock risk signals"
          description="Inventory risk data supports Operations and Inventory Planner decisions."
          columns={riskColumns}
          rows={stockRisks.slice(0, 8)}
          getRowKey={(row) => row.id || row.product_id || row.sku}
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
          getRowKey={(row) =>
            row.id ||
            `${row.product_id || row.sku || "na"}:${
              row.forecast_period_start || row.forecast_date || row.date || "na"
            }`
          }
          emptyMessage="Forecast endpoint returned no records. Check seed data and /forecasts API response."
        />

        <DataTable
          title="Products from backend"
          description="Product records remain visible as traceability evidence for dashboard metrics."
          columns={productColumns}
          rows={products.slice(0, 8)}
          getRowKey={(row) => row.id || row.sku}
          emptyMessage="Products endpoint returned no records. Check seed data and /products API response."
        />
      </DashboardSection>
    </main>
  );
}
