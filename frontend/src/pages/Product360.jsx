import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import {
  applyAlertWorkflowAction,
  applyRecommendationWorkflowAction,
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

function normalizeStatus(value, fallback) {
  return String(value || fallback || "open").toLowerCase();
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

function buildIdempotencyKey(entityType, entityId, action) {
  return ["frontend", "product-360", entityType, entityId, action, Date.now()].join(":");
}

function workflowErrorMessage(error, entityType) {
  if (error?.status === 404) {
    return `${formatTitle(entityType)} workflow endpoint or record was not found. Refresh Product 360 and verify the backend is running the current Sprint 10 API.`;
  }

  return error?.message || "Workflow action failed.";
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
        getProduct360(productId),
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
      getProduct360(productId),
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
          getProduct360(productId),
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

    const body = {
      idempotency_key: buildIdempotencyKey(entityType, entity.id, action),
    };

    if (workflowComment.trim()) {
      body.comment = workflowComment.trim();
    }

    const actionKey = `${entityType}:${entity.id}:${action}`;
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
  const canWriteWorkflow = hasPermission(state.user, "workflow:write");
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
          Product-level alerts and recommendations can now be actioned through
          Sprint 10 workflow write APIs. Access follows the selected demo user's
          workflow permissions.
        </p>
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
          <StatusBadge status={canWriteWorkflow ? "connected" : "warning"}>
            {canWriteWorkflow ? "workflow write" : "read only"}
          </StatusBadge>
          <span>{state.user?.display_name || selectedUserId}</span>
        </div>
        {workflowNotice ? (
          <p className={`action-queue-notice action-queue-notice--${workflowNotice.tone}`}>
            {workflowNotice.message}
          </p>
        ) : null}
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
        description="Operational alerts with Sprint 10 workflow actions."
        columns={alertWorkflowColumns}
        rows={state.data.alerts}
        emptyMessage="No alerts returned for this product."
      />

      <DataTable
        title="Recommendations"
        description="Product-level recommendations with accept, reject, dismiss and resolve actions."
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

        return (
          <button
            className="inline-action"
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
