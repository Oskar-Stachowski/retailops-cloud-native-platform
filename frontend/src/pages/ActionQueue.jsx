import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import {
  DistributionBars,
  InsightVisualCard,
  MiniBarList,
} from "../components/MiniVisualizations";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import {
  applyAlertWorkflowAction,
  applyRecommendationWorkflowAction,
  createWorkflowIdempotencyKey,
  getCurrentUser,
  getDashboardData,
  hasPermission,
} from "../services/retailopsApi";
import {
  getSelectedDemoUserId,
  subscribeDemoUserChanged,
} from "../auth/demoUser.js";
import "../styles/api-connected-ui.css";

const TERMINAL_STATUSES = new Set([
  "resolved",
  "dismissed",
  "rejected",
  "implemented",
  "closed",
]);

const ACTION_LABELS = {
  accept: "Accept",
  acknowledge: "Acknowledge",
  dismiss: "Dismiss",
  reject: "Reject",
  resolve: "Resolve",
};

const COMMENT_REQUIRED_ACTIONS = new Set(["dismiss", "reject"]);

const QUEUE_TYPE_COPY = {
  alert: {
    label: "Alert",
    groupTitle: "Alert decisions",
    groupDescription: "Operational signals requiring acknowledgement or resolution.",
  },
  recommendation: {
    label: "Recommendation",
    groupTitle: "Recommendation decisions",
    groupDescription: "Suggested commercial or inventory actions awaiting review.",
  },
};

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

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function normalizeStatus(value, fallback) {
  return String(value || fallback || "open").toLowerCase();
}

function normalizeSearchText(row) {
  return [
    row?.title,
    row?.recommended_action,
    row?.recommendation,
    row?.message,
    row?.description,
    row?.name,
    row?.action,
    row?.source,
    row?.type,
    row?.severity,
    row?.priority,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function containsAny(text, terms) {
  return terms.some((term) => text.includes(term));
}

function cleanActionText(value, fallback) {
  const text = String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!text) {
    return fallback;
  }

  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

function productIdentity(row) {
  const sku = firstPresent(row, ["sku", "product_sku"], "");
  const name = firstPresent(row, ["product_name", "productName"], "");
  const id = firstPresent(row, ["product_id", "productId"], "");

  return {
    sku,
    name,
    id,
    display: sku || name || id || "—",
  };
}

function alertTitle(alert) {
  const searchText = normalizeSearchText(alert);

  if (containsAny(searchText, ["sales drop", "revenue drop", "demand drop"])) {
    return "Investigate sales drop";
  }

  if (containsAny(searchText, ["stale inventory", "slow moving", "stale stock"])) {
    return "Review stale inventory";
  }

  if (containsAny(searchText, ["stockout", "stock out", "out of stock"])) {
    return "Resolve stockout risk";
  }

  if (containsAny(searchText, ["overstock", "excess inventory"])) {
    return "Review overstock exposure";
  }

  if (containsAny(searchText, ["price", "margin"])) {
    return "Review pricing anomaly";
  }

  const source = humanizeToken(firstPresent(alert, ["source", "type"], "alert signal"));
  return `Investigate ${source.toLowerCase()}`;
}

function recommendationTitle(recommendation) {
  const searchText = normalizeSearchText(recommendation);

  if (containsAny(searchText, ["replenish", "reorder", "stockout", "stock out"])) {
    return "Approve replenish stock";
  }

  if (containsAny(searchText, ["price", "markdown", "margin"])) {
    return "Review price recommendation";
  }

  if (containsAny(searchText, ["forecast", "demand"])) {
    return "Review demand forecast action";
  }

  const recommendedAction = firstPresent(
    recommendation,
    ["recommended_action", "recommendation", "action", "title"],
    "",
  );

  return cleanActionText(recommendedAction, "Review recommendation");
}

function queueDescription(item) {
  const source = humanizeToken(item.sourceType, "Operations");
  const product = item.queueProductDisplay && item.queueProductDisplay !== "—"
    ? ` · ${item.queueProductDisplay}`
    : "";
  const standalone = !item.queueId && item.queueType === "alert" ? " · Standalone action" : "";

  return `${source} signal${product}${standalone}`;
}

function buildActionQueue(data) {
  const alerts = (data?.alerts || []).map((alert) => {
    const product = productIdentity(alert);

    return {
      ...alert,
      queueType: "alert",
      queueId: alert.alert_id || (alert.source === "alert" ? alert.id : null),
      sourceId: alert.id,
      sourceType: alert.source || alert.type || "alert",
      queueTitle: alertTitle(alert),
      queueStatus: normalizeStatus(alert.status, "open"),
      queuePriority: firstPresent(alert, ["severity", "priority"], "normal"),
      queueProductDisplay: product.display,
      queueUpdatedAt: firstPresent(alert, ["updated_at", "created_at", "detected_at"], null),
      product_sku: product.sku,
      product_name: product.name,
      product_id: product.id,
    };
  });

  const recommendations = (data?.recommendations || []).map((recommendation) => {
    const product = productIdentity(recommendation);

    return {
      ...recommendation,
      queueType: "recommendation",
      queueId: recommendation.id,
      sourceId: recommendation.id,
      sourceType: recommendation.source || recommendation.type || "recommendation",
      queueTitle: recommendationTitle(recommendation),
      queueStatus: normalizeStatus(recommendation.status, "proposed"),
      queuePriority: firstPresent(recommendation, ["priority", "severity"], "normal"),
      queueProductDisplay: product.display,
      queueUpdatedAt: firstPresent(
        recommendation,
        ["generated_at", "updated_at", "created_at"],
        null,
      ),
      product_sku: product.sku,
      product_name: product.name,
      product_id: product.id,
    };
  });

  return [...alerts, ...recommendations].filter(
    (item) => item.sourceId && !TERMINAL_STATUSES.has(item.queueStatus),
  );
}

function availableActions(item) {
  if (!item.queueId) {
    return [];
  }

  if (item.queueType === "alert") {
    if (item.queueStatus === "open") {
      return ["acknowledge", "dismiss"];
    }

    if (["acknowledged", "in_progress"].includes(item.queueStatus)) {
      return ["resolve", "dismiss"];
    }

    return [];
  }

  if (item.queueStatus === "proposed") {
    return ["accept", "reject", "dismiss"];
  }

  if (item.queueStatus === "accepted") {
    return ["resolve"];
  }

  return [];
}

function actionVariant(action) {
  if (["accept", "acknowledge", "resolve"].includes(action)) {
    return "primary";
  }

  if (action === "reject") {
    return "danger";
  }

  return "secondary";
}

function workflowErrorMessage(error, item) {
  if (error?.status === 404 && item.queueType === "recommendation") {
    return (
      "Recommendation workflow endpoint or record was not found. Restart the " +
      "FastAPI backend with the current workflow routes and refresh the queue."
    );
  }

  if (error?.status === 404 && item.queueType === "alert") {
    return (
      "Alert workflow endpoint or linked alert was not found. Refresh the queue " +
      "and verify this row has a real alert_id."
    );
  }

  return error?.message || "Workflow action failed.";
}

function actionUnavailableReason(item, canWriteWorkflow) {
  if (!canWriteWorkflow) {
    return "Read-only role";
  }

  if (!item.queueId && item.queueType === "alert") {
    return "Standalone action";
  }

  if (!availableActions(item).length) {
    return "No action";
  }

  return null;
}

function groupQueueItems(items) {
  return ["alert", "recommendation"]
    .map((type) => ({
      type,
      ...QUEUE_TYPE_COPY[type],
      items: items.filter((item) => item.queueType === type),
    }))
    .filter((group) => group.items.length > 0);
}

function distributionItems(items, accessor, fallbackLabel = "Unknown") {
  const counts = new Map();

  for (const item of items || []) {
    const label = humanizeToken(accessor(item), fallbackLabel);
    counts.set(label, (counts.get(label) || 0) + 1);
  }

  return Array.from(counts, ([label, value]) => ({ label, value })).sort(
    (left, right) => right.value - left.value || left.label.localeCompare(right.label),
  );
}

export default function ActionQueue() {
  const [selectedUserId, setSelectedUserId] = useState(getSelectedDemoUserId());
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
    user: null,
  });
  const [comment, setComment] = useState("");
  const [activeAction, setActiveAction] = useState(null);
  const [notice, setNotice] = useState(null);
  const [workflowAttemptIds, setWorkflowAttemptIds] = useState({});

  const fetchQueueData = useCallback(
  async (userId) =>
    Promise.all([
      getDashboardData({ userId }),
      getCurrentUser({ userId }),
    ]),
  [],
);

  const loadQueue = useCallback(async (
    userId = selectedUserId,
    { showLoading = true } = {},
  ) => {
    if (showLoading) {
      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
    }

    try {
      const [data, user] = await fetchQueueData(userId);

      setState({
        loading: false,
        error: null,
        data,
        user,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        data: null,
        user: null,
      });
    }
  }, [fetchQueueData, selectedUserId]);

  useEffect(() => {
    let ignore = false;

    fetchQueueData(selectedUserId)
      .then(([data, user]) => {
        if (ignore) {
          return;
        }

        setState({
          loading: false,
          error: null,
          data,
          user,
        });
      })
      .catch((error) => {
        if (ignore) {
          return;
        }

        setState({
          loading: false,
          error,
          data: null,
          user: null,
        });
      });

    return () => {
      ignore = true;
    };
  }, [fetchQueueData, selectedUserId]);

  useEffect(() => subscribeDemoUserChanged(setSelectedUserId), []);

  const queueItems = useMemo(() => buildActionQueue(state.data), [state.data]);
  const queueGroups = useMemo(() => groupQueueItems(queueItems), [queueItems]);
  const canWriteWorkflow = hasPermission(state.user, "workflow:write");
  const alertCount = queueItems.filter((item) => item.queueType === "alert").length;
  const recommendationCount = queueItems.filter(
    (item) => item.queueType === "recommendation",
  ).length;
  const highPriorityCount = queueItems.filter((item) =>
    ["critical", "high"].includes(String(item.queuePriority).toLowerCase()),
  ).length;

  async function handleAction(item, action) {
    if (COMMENT_REQUIRED_ACTIONS.has(action) && comment.trim().length < 5) {
      setNotice({
        tone: "error",
        message: "Add a decision comment with at least 5 characters.",
      });
      return;
    }

    const actionKey = `${item.queueType}:${item.queueId}:${action}`;
    const workflowAttemptKey = `${selectedUserId}:${actionKey}`;
    const idempotencyKey =
      workflowAttemptIds[workflowAttemptKey] ||
      createWorkflowIdempotencyKey([item.queueType, item.queueId, action]);

    if (!workflowAttemptIds[workflowAttemptKey]) {
      setWorkflowAttemptIds((current) => ({
        ...current,
        [workflowAttemptKey]: idempotencyKey,
      }));
    }

    const body = {
      idempotency_key: idempotencyKey,
    };

    if (comment.trim()) {
      body.comment = comment.trim();
    }

    setActiveAction(actionKey);
    setNotice(null);

    try {
      if (item.queueType === "alert") {
        await applyAlertWorkflowAction(item.queueId, action, body, {
          userId: selectedUserId,
        });
      } else {
        await applyRecommendationWorkflowAction(item.queueId, action, body, {
          userId: selectedUserId,
        });
      }

      setComment("");
      setWorkflowAttemptIds((current) => {
        const next = { ...current };
        delete next[workflowAttemptKey];
        return next;
      });
      setNotice({
        tone: "success",
        message: `${ACTION_LABELS[action]} recorded for ${humanizeToken(item.queueType)}.`,
      });
      await loadQueue(selectedUserId, { showLoading: false });
    } catch (error) {
      setNotice({
        tone: "error",
        message: workflowErrorMessage(error, item),
      });
    } finally {
      setActiveAction(null);
    }
  }

  if (state.loading && !state.data) {
    return (
      <main className="api-page action-queue-page">
        <LoadingState title="Loading action queue" />
      </main>
    );
  }

  if (state.error && !state.data) {
    return (
      <main className="api-page action-queue-page">
        <ErrorState message={state.error.message} onRetry={() => loadQueue()} />
      </main>
    );
  }

  return (
    <main className="api-page action-queue-page">
      <PageHeader
        eyebrow="Workflow operations"
        title="Action queue"
        description="Operational alerts and recommendations are grouped into a decision queue with role-aware, auditable workflow actions."
        className="action-queue-header"
        actions={
          <button
            className="secondary-button"
            type="button"
            onClick={() => loadQueue()}
            disabled={state.loading}
          >
            Refresh
          </button>
        }
      />

      <section className="metrics-grid" aria-label="Action queue summary">
        <MetricCard
          label="Queue items"
          value={queueItems.length}
          helper="Pending workflow decisions"
          status={queueItems.length > 0 ? "Open" : "Clear"}
          tone={queueItems.length > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="Alert decisions"
          value={alertCount}
          helper="Operational signals requiring action"
          status={alertCount > 0 ? "Open" : "Clear"}
          tone={alertCount > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="Recommendations"
          value={recommendationCount}
          helper="Suggested commercial actions"
          status={recommendationCount > 0 ? "Review" : "Clear"}
          tone="neutral"
        />
        <MetricCard
          label="High priority"
          value={highPriorityCount}
          helper="Critical and high-severity records"
          status={highPriorityCount > 0 ? "High" : "Clear"}
          tone={highPriorityCount > 0 ? "danger" : "success"}
        />
        <MetricCard
          label="Workflow access"
          value={canWriteWorkflow ? "Write" : "Read only"}
          helper={state.user?.display_name || selectedUserId}
          status={canWriteWorkflow ? "Enabled" : "Limited"}
          tone={canWriteWorkflow ? "success" : "warning"}
        />
      </section>


      <section className="mini-visual-grid mini-visual-grid--two">
        <InsightVisualCard
          eyebrow="Workflow status"
          title="Queue by status"
          description="A quick view of how pending decisions are distributed."
        >
          <DistributionBars
            items={distributionItems(queueItems, (item) => item.queueStatus, "Open")}
            emptyMessage="No pending queue status data available."
          />
        </InsightVisualCard>

        <InsightVisualCard
          eyebrow="Priority mix"
          title="Decision priority bars"
          description="Highlights whether the queue contains high-severity work."
        >
          <MiniBarList
            items={distributionItems(queueItems, (item) => item.queuePriority, "Normal")}
            emptyMessage="No queue priority data available."
          />
        </InsightVisualCard>
      </section>

      <section className="action-queue-workspace">
        <section className="table-card action-queue-table">
          <header className="table-card__header">
            <h2>Pending decisions</h2>
            <p>
              Primary actions move work forward. Reject and dismiss actions require
              a short decision comment.
            </p>
          </header>
          {queueItems.length ? (
            <div className="table-card__scroll">
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Type</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Product</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {queueGroups.map((group) => (
                    <Fragment key={group.type}>
                      <tr className="action-queue-group-row">
                        <td colSpan="7">
                          <strong>{group.groupTitle}</strong>
                          <span>{group.groupDescription}</span>
                        </td>
                      </tr>
                      {group.items.map((item) => (
                        <tr key={`${item.queueType}:${item.queueId || item.sourceId}`}>
                          <td>
                            <span className="action-queue-item">
                              <strong>{item.queueTitle}</strong>
                              <span>{queueDescription(item)}</span>
                            </span>
                          </td>
                          <td>
                            <span className={`queue-type-pill queue-type-pill--${item.queueType}`}>
                              {QUEUE_TYPE_COPY[item.queueType]?.label || humanizeToken(item.queueType)}
                            </span>
                          </td>
                          <td>
                            <StatusBadge status={item.queuePriority} />
                          </td>
                          <td>
                            <StatusBadge status={item.queueStatus} />
                          </td>
                          <td>
                            <ProductReferenceCell row={item} />
                          </td>
                          <td>{formatDateTime(item.queueUpdatedAt)}</td>
                          <td>
                            <div className="action-button-group">
                              {availableActions(item).map((action) => {
                                const actionKey = `${item.queueType}:${item.queueId}:${action}`;
                                const variant = actionVariant(action);

                                return (
                                  <button
                                    className={`inline-action inline-action--${variant}`}
                                    type="button"
                                    key={action}
                                    onClick={() => handleAction(item, action)}
                                    disabled={!canWriteWorkflow || activeAction === actionKey}
                                  >
                                    {activeAction === actionKey ? "Saving" : ACTION_LABELS[action]}
                                  </button>
                                );
                              })}
                              {actionUnavailableReason(item, canWriteWorkflow) ? (
                                <span className="action-queue-unavailable">
                                  {actionUnavailableReason(item, canWriteWorkflow)}
                                </span>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="action-queue-empty">
              <h3>No pending workflow actions</h3>
              <p>
                All actionable alerts and recommendations are resolved or the dashboard
                endpoints did not return open workflow records.
              </p>
            </div>
          )}
        </section>

        <aside className="action-queue-side-panel" aria-label="Decision support">
          <section className="action-queue-controls">
            <label htmlFor="queue-comment">
              Decision comment
              <textarea
                id="queue-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Required for Reject and Dismiss. Example: supplier stock checked, no action needed."
                rows={4}
              />
            </label>
            {notice ? (
              <p className={`action-queue-notice action-queue-notice--${notice.tone}`}>
                {notice.message}
              </p>
            ) : null}
          </section>

          <section className="action-queue-guidance">
            <h3>Decision model</h3>
            <ul>
              <li><strong>Accept</strong> moves a recommendation forward.</li>
              <li><strong>Acknowledge</strong> confirms alert ownership.</li>
              <li><strong>Resolve</strong> closes completed operational work.</li>
              <li><strong>Dismiss / Reject</strong> records a controlled no-go decision.</li>
            </ul>
          </section>
        </aside>
      </section>
    </main>
  );
}
