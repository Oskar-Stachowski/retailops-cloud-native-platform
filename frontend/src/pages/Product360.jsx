import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import {
  DistributionBars,
  InsightVisualCard,
  LineSparkChart,
  MiniBarList,
} from "../components/MiniVisualizations.jsx";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import {
  applyAlertWorkflowAction,
  applyRecommendationWorkflowAction,
  createWorkflowIdempotencyKey,
  getCurrentUser,
  getProduct360,
  hasPermission,
} from "../services/retailopsApi";
import {
  getSelectedDemoUserId,
  subscribeDemoUserChanged,
} from "../auth/demoUser.js";
import "../styles/api-connected-ui.css";

const ACTION_LABELS = {
  accept: "Accept",
  acknowledge: "Acknowledge",
  dismiss: "Dismiss",
  reject: "Reject",
  resolve: "Resolve",
};

const COMMENT_REQUIRED_ACTIONS = new Set(["dismiss", "reject"]);
const PRODUCT_360_RELATED_LIMIT = 50;

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

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
  });
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

function formatCurrencyWithUnit(value, currency = "USD") {
  return `${formatCurrency(value)} ${currency}`;
}

function formatInteger(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 0,
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

function normalizeStatus(value, fallback) {
  return String(value || fallback || "open").toLowerCase();
}

function normalizeCollection(value) {
  return Array.isArray(value) ? value : [];
}

function toFiniteNumber(value) {
  const numberValue = Number(value);

  return Number.isFinite(numberValue) ? numberValue : null;
}

function dateKey(value) {
  if (!value) {
    return null;
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toISOString().slice(0, 10);
}

function revenueFromSale(row) {
  const totalAmount = toFiniteNumber(row.total_amount ?? row.revenue);

  if (totalAmount !== null) {
    return totalAmount;
  }

  const quantity = toFiniteNumber(row.quantity);
  const unitPrice = toFiniteNumber(row.unit_price);

  if (quantity === null || unitPrice === null) {
    return null;
  }

  return quantity * unitPrice;
}

function aggregateSalesByDate(items) {
  const dailySales = new Map();

  normalizeCollection(items).forEach((row) => {
    const key = dateKey(row.sold_at);
    const revenue = revenueFromSale(row);

    if (!key || revenue === null) {
      return;
    }

    const current = dailySales.get(key) || {
      date: key,
      revenue: 0,
      quantity: 0,
      currency: row.currency || "USD",
    };
    current.revenue += revenue;
    current.quantity += toFiniteNumber(row.quantity) ?? 0;
    current.currency = current.currency || row.currency || "USD";
    dailySales.set(key, current);
  });

  return sortedByDate(Array.from(dailySales.values()), (row) => row.date);
}

function aggregateInventoryByDate(items) {
  const dailyInventory = new Map();

  normalizeCollection(items).forEach((row) => {
    const key = dateKey(row.recorded_at);
    const stockQuantity = toFiniteNumber(row.stock_quantity);

    if (!key || stockQuantity === null) {
      return;
    }

    const current = dailyInventory.get(key) || {
      date: key,
      stock_quantity: 0,
      unit_of_measure: row.unit_of_measure || "units",
    };
    current.stock_quantity += stockQuantity;
    current.unit_of_measure = current.unit_of_measure || row.unit_of_measure || "units";
    dailyInventory.set(key, current);
  });

  return sortedByDate(Array.from(dailyInventory.values()), (row) => row.date);
}

function countBy(items, accessor) {
  const counts = new Map();

  normalizeCollection(items).forEach((item) => {
    const rawLabel = accessor(item) || "unknown";
    const label = formatTitle(rawLabel);

    counts.set(label, (counts.get(label) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((left, right) => right.value - left.value);
}

function sortedByDate(items, accessor) {
  return [...normalizeCollection(items)].sort((left, right) => {
    const leftTime = new Date(accessor(left) || 0).getTime();
    const rightTime = new Date(accessor(right) || 0).getTime();

    return leftTime - rightTime;
  });
}

function riskTone(status) {
  const normalized = normalizeStatus(status, "unknown");

  if (normalized === "normal") {
    return "success";
  }

  if (["stockout_risk", "critical", "high"].includes(normalized)) {
    return "danger";
  }

  if (["overstock_risk", "medium", "warning"].includes(normalized)) {
    return "warning";
  }

  return "neutral";
}

function actionTone(action) {
  if (["accept", "acknowledge", "resolve"].includes(action)) {
    return "primary";
  }

  if (action === "reject") {
    return "danger";
  }

  return "secondary";
}

function latestActivity(metrics) {
  return (
    metrics.latest_sale_at ||
    metrics.inventory_updated_at ||
    metrics.latest_forecast_period_end ||
    metrics.latest_forecast_period_start
  );
}

function availableAlertActions(alert) {
  const status = normalizeStatus(alert.status, "open");

  if (status === "open") {
    return ["acknowledge", "dismiss"];
  }

  if (["acknowledged", "in_progress"].includes(status)) {
    return ["resolve", "dismiss"];
  }

  return [];
}

function availableRecommendationActions(recommendation) {
  const status = normalizeStatus(recommendation.status, "proposed");

  if (status === "proposed") {
    return ["accept", "reject", "dismiss"];
  }

  if (status === "accepted") {
    return ["resolve"];
  }

  return [];
}

function workflowErrorMessage(error, entityType) {
  if (error?.status === 404) {
    return `${formatTitle(entityType)} workflow endpoint or record was not found. Refresh Product 360 and verify the backend is running the current workflow API.`;
  }

  return error?.message || "Workflow action failed.";
}

function Product360Section({ id, eyebrow, title, description, children }) {
  return (
    <section className="api-page__section product-360-section" id={id}>
      <header className="section-heading">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </header>
      {children}
    </section>
  );
}

function DecisionPreviewCard({ eyebrow, title, status, description, children }) {
  return (
    <article className="product-360-decision-card">
      <div className="product-360-decision-card__header">
        <div>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h3>{title}</h3>
        </div>
        {status ? <StatusBadge status={status}>{formatTitle(status)}</StatusBadge> : null}
      </div>
      {description ? <p>{description}</p> : null}
      {children}
    </article>
  );
}

export default function Product360() {
  const { productId } = useParams();
  const [selectedUserId, setSelectedUserId] = useState(getSelectedDemoUserId());
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
    productId: null,
    user: null,
  });
  const [workflowComment, setWorkflowComment] = useState("");
  const [activeWorkflowAction, setActiveWorkflowAction] = useState(null);
  const [workflowNotice, setWorkflowNotice] = useState(null);
  const [workflowAttemptIds, setWorkflowAttemptIds] = useState({});

  const handleRetry = useCallback(async () => {
    setState({
      loading: true,
      error: null,
      data: null,
      productId,
      user: null,
    });

    try {
      const [data, user] = await Promise.all([
        getProduct360(productId, { limit: PRODUCT_360_RELATED_LIMIT }),
        getCurrentUser({ userId: selectedUserId }),
      ]);

      setState({
        loading: false,
        error: null,
        data,
        productId,
        user,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        data: null,
        productId,
        user: null,
      });
    }
  }, [productId, selectedUserId]);

  const refreshProduct360 = useCallback(async () => {
    const [data, user] = await Promise.all([
      getProduct360(productId, { limit: PRODUCT_360_RELATED_LIMIT }),
      getCurrentUser({ userId: selectedUserId }),
    ]);

    setState({
      loading: false,
      error: null,
      data,
      productId,
      user,
    });
  }, [productId, selectedUserId]);

  useEffect(() => {
    let isCurrent = true;

    async function loadInitialProduct360() {
      try {
        const [data, user] = await Promise.all([
          getProduct360(productId, { limit: PRODUCT_360_RELATED_LIMIT }),
          getCurrentUser({ userId: selectedUserId }),
        ]);

        if (isCurrent) {
          setState({
            loading: false,
            error: null,
            data,
            productId,
            user,
          });
        }
      } catch (error) {
        if (isCurrent) {
          setState({
            loading: false,
            error,
            data: null,
            productId,
            user: null,
          });
        }
      }
    }

    loadInitialProduct360();

    return () => {
      isCurrent = false;
    };
  }, [productId, selectedUserId]);

  useEffect(() => subscribeDemoUserChanged(setSelectedUserId), []);

  async function handleWorkflowAction(entityType, entity, action) {
    if (COMMENT_REQUIRED_ACTIONS.has(action) && workflowComment.trim().length < 5) {
      setWorkflowNotice({
        tone: "error",
        message: "Add a decision comment with at least 5 characters.",
      });
      return;
    }

    const actionKey = `${entityType}:${entity.id}:${action}`;
    const workflowAttemptKey = `${selectedUserId}:${productId}:${actionKey}`;
    const idempotencyKey =
      workflowAttemptIds[workflowAttemptKey] ||
      createWorkflowIdempotencyKey(["product-360", entityType, entity.id, action]);
    const body = {
      idempotency_key: idempotencyKey,
    };

    if (workflowComment.trim()) {
      body.comment = workflowComment.trim();
    }

    if (!workflowAttemptIds[workflowAttemptKey]) {
      setWorkflowAttemptIds((current) => ({
        ...current,
        [workflowAttemptKey]: idempotencyKey,
      }));
    }

    setActiveWorkflowAction(actionKey);
    setWorkflowNotice(null);

    try {
      if (entityType === "alert") {
        await applyAlertWorkflowAction(entity.id, action, body, {
          userId: selectedUserId,
        });
      } else {
        await applyRecommendationWorkflowAction(entity.id, action, body, {
          userId: selectedUserId,
        });
      }

      setWorkflowAttemptIds((current) => {
        if (!current[workflowAttemptKey]) {
          return current;
        }

        const next = { ...current };
        delete next[workflowAttemptKey];
        return next;
      });
      setWorkflowComment("");
      setWorkflowNotice({
        tone: "success",
        message: `${ACTION_LABELS[action]} recorded for ${formatTitle(entityType)}.`,
      });
      await refreshProduct360();
    } catch (error) {
      setWorkflowNotice({
        tone: "error",
        message: workflowErrorMessage(error, entityType),
      });
    } finally {
      setActiveWorkflowAction(null);
    }
  }

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
  const sales = normalizeCollection(state.data.sales);
  const inventorySnapshots = normalizeCollection(state.data.inventory_snapshots);
  const forecasts = normalizeCollection(state.data.forecasts);
  const anomalies = normalizeCollection(state.data.anomalies);
  const alerts = normalizeCollection(state.data.alerts);
  const recommendations = normalizeCollection(state.data.recommendations);
  const workflowActions = normalizeCollection(state.data.workflow_actions);
  const canWriteWorkflow = hasPermission(state.user, "workflow:write");
  const salesTrend = aggregateSalesByDate(sales);
  const inventoryTrend = aggregateInventoryByDate(inventorySnapshots);
  const salesCurrency = salesTrend.find((row) => row.currency)?.currency || "USD";
  const inventoryUnit = inventoryTrend.find((row) => row.unit_of_measure)?.unit_of_measure || "units";
  const salesTrendEmptyMessage = sales.length
    ? "At least two sales dates are required to show a revenue movement chart."
    : "No sales records returned for this product.";
  const topAlert = alerts[0];
  const topRecommendation = recommendations[0];
  const relatedLimit = state.data.limits?.related_items || 10;

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
    { header: "Type", accessor: (row) => formatTitle(row.alert_type) },
    {
      header: "Severity",
      render: (row) => <StatusBadge status={row.severity}>{row.severity}</StatusBadge>,
    },
    {
      header: "Status",
      render: (row) => <StatusBadge status={row.status}>{row.status}</StatusBadge>,
    },
    { header: "Recommended action", accessor: "recommended_action" },
  ];

  const recommendationColumns = [
    { header: "Recommendation", accessor: "recommended_action" },
    { header: "Type", accessor: (row) => formatTitle(row.recommendation_type) },
    {
      header: "Status",
      render: (row) => <StatusBadge status={row.status}>{row.status}</StatusBadge>,
    },
    { header: "Generated", accessor: (row) => formatDateTime(row.generated_at) },
    {
      header: "Workflow",
      render: (row) => (
        <WorkflowActionButtons
          actions={availableRecommendationActions(row)}
          activeAction={activeWorkflowAction}
          canWriteWorkflow={canWriteWorkflow}
          entity={row}
          entityType="recommendation"
          onAction={handleWorkflowAction}
        />
      ),
    },
  ];

  const alertWorkflowColumns = [
    ...alertColumns,
    {
      header: "Workflow",
      render: (row) => (
        <WorkflowActionButtons
          actions={availableAlertActions(row)}
          activeAction={activeWorkflowAction}
          canWriteWorkflow={canWriteWorkflow}
          entity={row}
          entityType="alert"
          onAction={handleWorkflowAction}
        />
      ),
    },
  ];

  const workflowColumns = [
    { header: "Action", accessor: (row) => formatTitle(row.action_type) },
    { header: "Alert", accessor: (row) => row.alert_title || "Standalone action" },
    { header: "User", accessor: (row) => row.performed_by_login || "—" },
    {
      header: "Status change",
      accessor: (row) => `${row.previous_status || "—"} → ${row.new_status || "—"}`,
    },
    { header: "Performed", accessor: (row) => formatDateTime(row.performed_at) },
  ];

  return (
    <main className="api-page product-360-page">
      <PageHeader
        eyebrow="Product 360"
        title={product.name}
        description={`SKU ${product.sku} · ${product.category || "No category"} · ${
          product.brand || "No brand"
        }`}
        actions={(
          <>
            <StatusBadge status={product.status}>{product.status}</StatusBadge>
            <Link className="inline-link" to="/products">← Back to products</Link>
          </>
        )}
        className="product-360-header"
      />

      <section className="product-360-sticky-summary" aria-label="Product 360 summary">
        <div className="product-360-sticky-summary__identity">
          <span className="eyebrow">Current product</span>
          <strong>{product.sku}</strong>
          <span>{product.category || "Uncategorized"}</span>
        </div>
        <div className="product-360-sticky-summary__signals">
          <span>
            Risk <strong>{formatTitle(metrics.risk_status)}</strong>
          </span>
          <span>
            Stock <strong>{formatInteger(metrics.current_stock)}</strong>
          </span>
          <span>
            Alerts <strong>{metrics.open_alert_count}</strong>
          </span>
          <span>
            Latest <strong>{formatDateTime(latestActivity(metrics))}</strong>
          </span>
        </div>
        <nav className="product-360-anchor-nav" aria-label="Product 360 sections">
          <a href="#product360-overview">Overview</a>
          <a href="#product360-sales-inventory">Sales</a>
          <a href="#product360-forecast">Forecast</a>
          <a href="#product360-workflow">Workflow</a>
          <a href="#product360-evidence">Evidence</a>
        </nav>
      </section>

      <Product360Section
        id="product360-overview"
        eyebrow="Decision center"
        title="Product health and priority signals"
        description="A recruiter-friendly summary of commercial performance, stock risk and decision backlog before the detailed evidence tables."
      >
        <section className="metrics-grid product-360-metrics-grid">
          <MetricCard
            label="Risk status"
            value={formatTitle(metrics.risk_status)}
            helper="From stock risk model"
            tone={riskTone(metrics.risk_status)}
          />
          <MetricCard
            label="Current stock"
            value={formatInteger(metrics.current_stock)}
            helper="Latest inventory snapshot"
          />
          <MetricCard
            label="Forecast qty"
            value={formatInteger(metrics.latest_forecast_quantity)}
            helper="Latest demand signal"
          />
          <MetricCard
            label="Revenue"
            value={formatCurrency(metrics.total_revenue)}
            helper="Sales evidence"
          />
          <MetricCard
            label="Open alerts"
            value={metrics.open_alert_count}
            helper="Operational backlog"
            tone={metrics.open_alert_count > 0 ? "warning" : "success"}
          />
          <MetricCard
            label="Recommendations"
            value={metrics.open_recommendation_count}
            helper="Proposed actions"
          />
        </section>

        <div className="product-360-priority-grid">
          <DecisionPreviewCard
            eyebrow="Top alert"
            title={topAlert?.title || "No open alert returned"}
            status={topAlert?.severity || "normal"}
            description={topAlert?.recommended_action || "No urgent product alert is in scope."}
          />
          <DecisionPreviewCard
            eyebrow="Top recommendation"
            title={topRecommendation?.recommended_action || "No recommendation returned"}
            status={topRecommendation?.status || "normal"}
            description={topRecommendation?.rationale || "No proposed product action is in scope."}
          />
          <DecisionPreviewCard
            eyebrow="Evidence depth"
            title={`${relatedLimit} rows per evidence section`}
            status="connected"
            description="The Product 360 API composes product, sales, inventory, forecast, anomaly, alert, recommendation and workflow data."
          />
        </div>
      </Product360Section>

      <Product360Section
        id="product360-sales-inventory"
        eyebrow="Commercial and inventory context"
        title="Sales and stock movement"
        description="Mini-visualizations keep the screen scannable before the detailed rows."
      >
        <div className="mini-visual-grid mini-visual-grid--two">
          <InsightVisualCard
            eyebrow="Sales"
            title="Revenue movement"
            description="Daily revenue aggregated from returned sales records."
          >
            <LineSparkChart
              rows={salesTrend.length >= 2 ? salesTrend : []}
              valueAccessor={(row) => row.revenue}
              labelAccessor={(row) => formatDate(row.date)}
              valueFormatter={(value) => formatCurrencyWithUnit(value, salesCurrency)}
              emptyMessage={salesTrendEmptyMessage}
            />
          </InsightVisualCard>
          <InsightVisualCard
            eyebrow="Inventory"
            title="Stock snapshots"
            description={`Daily units on hand aggregated from returned inventory snapshots (${inventoryUnit}).`}
          >
            <LineSparkChart
              rows={inventoryTrend}
              valueAccessor={(row) => row.stock_quantity}
              labelAccessor={(row) => formatDate(row.date)}
              valueFormatter={(value) => `${formatInteger(value)} ${inventoryUnit}`}
              emptyMessage="No inventory snapshots returned for this product."
            />
          </InsightVisualCard>
        </div>

        <DataTable
          title="Recent sales"
          description="Sales evidence behind Product 360 commercial context."
          columns={salesColumns}
          rows={sales}
          getRowKey={(row) => row.id || `${row.sold_at || "na"}:${row.channel || "na"}`}
          emptyMessage="No sales records returned for this product."
        />

        <DataTable
          title="Inventory snapshots"
          description="Latest inventory evidence used for stock-risk decisions."
          columns={inventoryColumns}
          rows={inventorySnapshots}
          getRowKey={(row) => row.id || `${row.recorded_at || "na"}:${row.warehouse_code || "na"}`}
          emptyMessage="No inventory snapshots returned for this product."
        />
      </Product360Section>

      <Product360Section
        id="product360-forecast"
        eyebrow="Demand planning"
        title="Forecast and stock-risk context"
        description="Demand confidence and stock-risk status are shown above the raw records."
      >
        <div className="mini-visual-grid mini-visual-grid--two">
          <InsightVisualCard
            eyebrow="Forecast"
            title="Confidence levels"
            description="Confidence attached to forecast records."
          >
            <MiniBarList
              items={forecasts.map((row) => ({
                label: formatDateRange(row.forecast_period_start, row.forecast_period_end),
                value: Number(row.confidence_level) * 100,
                valueLabel: formatPercent(row.confidence_level),
              }))}
              emptyMessage="No forecast confidence rows returned for this product."
            />
          </InsightVisualCard>
          <InsightVisualCard
            eyebrow="Risk"
            title="Risk signal breakdown"
            description="Current product risk and linked anomaly severity."
          >
            <DistributionBars
              items={[
                { label: formatTitle(metrics.risk_status), value: stockRisk ? 1 : 0 },
                ...countBy(anomalies, (row) => row.severity),
              ]}
              emptyMessage="No stock-risk or anomaly signal returned for this product."
            />
          </InsightVisualCard>
        </div>

        <DataTable
          title="Stock risk"
          description="Single product stock-risk context used by inventory planners."
          columns={[
            {
              header: "Product",
              render: (row) => (
                <ProductReferenceCell
                  row={{
                    product_id: row.product_id,
                    product_name: row.name || product.name,
                    sku: row.sku || product.sku,
                  }}
                />
              ),
            },
            { header: "Current stock", accessor: "current_stock" },
            { header: "Forecast", accessor: "forecast_quantity" },
            {
              header: "Risk",
              render: (row) => (
                <StatusBadge status={row.risk_status}>{formatTitle(row.risk_status)}</StatusBadge>
              ),
            },
          ]}
          rows={stockRisk ? [stockRisk] : []}
          getRowKey={(row) => row.product_id || row.sku}
          emptyMessage="No stock-risk row is available for this product yet."
        />

        <DataTable
          title="Forecast records"
          description="Demand-planning records linked to the product."
          columns={forecastColumns}
          rows={forecasts}
          getRowKey={(row) => row.id || `${row.forecast_period_start || "na"}:${row.method || "na"}`}
          emptyMessage="No forecasts returned for this product."
        />
      </Product360Section>

      <Product360Section
        id="product360-workflow"
        eyebrow="Workflow"
        title="Decision actions"
        description="Alerts and recommendations can be actioned without scrolling through every historical table first."
      >
        <section className="feature-boundary product-360-workflow-boundary">
          <div className="feature-boundary__intro">
            <h2>Operational workflow boundary</h2>
            <p>
              Product-level alerts and recommendations can be actioned through workflow write APIs.
              Access follows the selected demo user's workflow permissions.
            </p>
          </div>
          <div className="product-360-workflow-summary">
            <StatusBadge status={canWriteWorkflow ? "connected" : "warning"}>
              {canWriteWorkflow ? "workflow write" : "read only"}
            </StatusBadge>
            <span>{state.user?.display_name || selectedUserId}</span>
          </div>
        </section>

        <section className="action-queue-controls product-360-workflow-controls">
          <label htmlFor="product-workflow-comment">
            Decision comment
            <textarea
              id="product-workflow-comment"
              value={workflowComment}
              onChange={(event) => setWorkflowComment(event.target.value)}
              placeholder="Required for reject and dismiss actions."
              rows={3}
            />
          </label>
          <div className="product-360-workflow-access">
            <span>Primary: accept, acknowledge, resolve</span>
            <span>Secondary: dismiss · Destructive: reject</span>
          </div>
          {workflowNotice ? (
            <p className={`action-queue-notice action-queue-notice--${workflowNotice.tone}`}>
              {workflowNotice.message}
            </p>
          ) : null}
        </section>

        <DataTable
          title="Alerts"
          description="Operational alerts with workflow actions."
          columns={alertWorkflowColumns}
          rows={alerts}
          getRowKey={(row) => row.id || row.alert_id || `${row.title || "alert"}:${row.created_at || "na"}`}
          emptyMessage="No alerts returned for this product."
        />

        <DataTable
          title="Recommendations"
          description="Product-level recommendations with accept, reject, dismiss and resolve actions."
          columns={recommendationColumns}
          rows={recommendations}
          getRowKey={(row) => row.id || `${row.recommended_action || "recommendation"}:${row.created_at || "na"}`}
          emptyMessage="No recommendations returned for this product."
        />
      </Product360Section>

      <Product360Section
        id="product360-evidence"
        eyebrow="Traceable evidence"
        title="Historical rows and audit trail"
        description="Detailed evidence stays available, but it no longer dominates the first screen."
      >
        <div className="mini-visual-grid mini-visual-grid--two">
          <InsightVisualCard
            eyebrow="Alerts"
            title="Severity distribution"
            description="Open product alert severity in the returned result set."
          >
            <DistributionBars
              items={countBy(alerts, (row) => row.severity)}
              emptyMessage="No alert severity rows returned for this product."
            />
          </InsightVisualCard>
          <InsightVisualCard
            eyebrow="Workflow"
            title="Action audit mix"
            description="Workflow actions grouped by recorded action type."
          >
            <DistributionBars
              items={countBy(workflowActions, (row) => row.action_type)}
              emptyMessage="No workflow audit rows returned for this product."
            />
          </InsightVisualCard>
        </div>

        <DataTable
          title="Anomalies"
          description="Product-level anomaly signals from operational data."
          columns={anomalyColumns}
          rows={anomalies}
          getRowKey={(row) => row.id || `${row.detected_at || "na"}:${row.metric_name || "na"}`}
          emptyMessage="No anomalies returned for this product."
        />

        <DataTable
          title="Workflow actions"
          description="Audit trail linked through product alerts."
          columns={workflowColumns}
          rows={workflowActions}
          getRowKey={(row) => row.id || `${row.performed_at || "na"}:${row.action_type || "na"}`}
          emptyMessage="No workflow actions returned for this product."
        />
      </Product360Section>
    </main>
  );
}

function WorkflowActionButtons({
  actions,
  activeAction,
  canWriteWorkflow,
  entity,
  entityType,
  onAction,
}) {
  if (!actions.length) {
    return <span className="action-queue-unavailable">No action</span>;
  }

  if (!canWriteWorkflow) {
    return <span className="action-queue-unavailable">Read-only role</span>;
  }

  return (
    <div className="action-button-group">
      {actions.map((action) => {
        const actionKey = `${entityType}:${entity.id}:${action}`;
        const className = `inline-action inline-action--${actionTone(action)}`;

        return (
          <button
            className={className}
            key={action}
            type="button"
            onClick={() => onAction(entityType, entity, action)}
            disabled={activeAction === actionKey}
          >
            {activeAction === actionKey ? "Saving" : ACTION_LABELS[action]}
          </button>
        );
      })}
    </div>
  );
}
