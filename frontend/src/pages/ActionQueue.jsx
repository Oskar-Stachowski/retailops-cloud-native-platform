import { useCallback, useEffect, useMemo, useState } from "react";

import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
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

function itemTitle(row) {
  return firstPresent(
    row,
    [
      "title",
      "recommended_action",
      "recommendation",
      "message",
      "description",
      "name",
      "action",
    ],
    "Operational action",
  );
}

function productReference(row) {
  return firstPresent(row, ["sku", "product_sku", "product_id"]);
}

function buildActionQueue(data) {
  const alerts = (data?.alerts || []).map((alert) => ({
    ...alert,
    queueType: "alert",
    queueId: alert.alert_id || (alert.source === "alert" ? alert.id : null),
    sourceId: alert.id,
    sourceType: alert.source || "alert",
    queueTitle: itemTitle(alert),
    queueStatus: normalizeStatus(alert.status, "open"),
    queuePriority: firstPresent(alert, ["severity", "priority"], "normal"),
    queueProduct: productReference(alert),
    queueUpdatedAt: firstPresent(alert, ["updated_at", "created_at", "detected_at"], null),
  }));

  const recommendations = (data?.recommendations || []).map((recommendation) => ({
    ...recommendation,
    queueType: "recommendation",
    queueId: recommendation.id,
    sourceId: recommendation.id,
    sourceType: recommendation.source || "recommendation",
    queueTitle: itemTitle(recommendation),
    queueStatus: normalizeStatus(recommendation.status, "proposed"),
    queuePriority: firstPresent(recommendation, ["priority", "severity"], "normal"),
    queueProduct: productReference(recommendation),
    queueUpdatedAt: firstPresent(
      recommendation,
      ["generated_at", "updated_at", "created_at"],
      null,
    ),
  }));

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
    return "No linked alert";
  }

  if (!availableActions(item).length) {
    return "No action";
  }

  return null;
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
      const [data, user] = await Promise.all([
        getDashboardData({ userId }),
        getCurrentUser({ userId }),
      ]);

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
  }, [selectedUserId]);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialQueue() {
      try {
        const [data, user] = await Promise.all([
          getDashboardData({ userId: selectedUserId }),
          getCurrentUser({ userId: selectedUserId }),
        ]);

        if (isMounted) {
          setState({
            loading: false,
            error: null,
            data,
            user,
          });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            loading: false,
            error,
            data: null,
            user: null,
          });
        }
      }
    }

    loadInitialQueue();

    return () => {
      isMounted = false;
    };
  }, [selectedUserId]);

  useEffect(() => subscribeDemoUserChanged(setSelectedUserId), []);

  const queueItems = useMemo(() => buildActionQueue(state.data), [state.data]);
  const canWriteWorkflow = hasPermission(state.user, "workflow:write");
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
      await loadQueue(selectedUserId);
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
    return <LoadingState title="Loading action queue" />;
  }

  if (state.error && !state.data) {
    return <ErrorState message={state.error.message} onRetry={() => loadQueue()} />;
  }

  return (
    <main className="api-page action-queue-page">
      <header className="api-page__header action-queue-header">
        <div>
          <p className="eyebrow">Workflow operations</p>
          <h1>Action queue</h1>
          <p>
            Open alerts and recommendations are grouped into one operator queue
            with role-aware workflow actions.
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => loadQueue()}
          disabled={state.loading}
        >
          Refresh
        </button>
      </header>

      <section className="metrics-grid" aria-label="Action queue summary">
        <MetricCard
          label="Queue items"
          value={queueItems.length}
          helper="Actionable alerts and recommendations"
          tone={queueItems.length > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="High priority"
          value={highPriorityCount}
          helper="Critical and high-severity records"
          tone={highPriorityCount > 0 ? "risk" : "positive"}
        />
        <MetricCard
          label="Workflow access"
          value={canWriteWorkflow ? "Write" : "Read only"}
          helper={state.user?.display_name || selectedUserId}
          tone={canWriteWorkflow ? "positive" : "warning"}
        />
      </section>

      <section className="action-queue-controls">
        <label htmlFor="queue-comment">
          Decision comment
          <textarea
            id="queue-comment"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Required for reject and dismiss actions."
            rows={3}
          />
        </label>
        {notice ? (
          <p className={`action-queue-notice action-queue-notice--${notice.tone}`}>
            {notice.message}
          </p>
        ) : null}
      </section>

      <section className="table-card action-queue-table">
        <header className="table-card__header">
          <h2>Pending decisions</h2>
          <p>
            Actions are sent to workflow write endpoints using the
            selected demo user.
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
                {queueItems.map((item) => (
                  <tr key={`${item.queueType}:${item.queueId}`}>
                    <td>
                      <strong>{item.queueTitle}</strong>
                    </td>
                    <td>{humanizeToken(item.queueType)}</td>
                    <td>
                      <StatusBadge status={item.queuePriority} />
                    </td>
                    <td>
                      <StatusBadge status={item.queueStatus} />
                    </td>
                    <td>{item.queueProduct}</td>
                    <td>{formatDateTime(item.queueUpdatedAt)}</td>
                    <td>
                      <div className="action-button-group">
                        {availableActions(item).map((action) => {
                          const actionKey = `${item.queueType}:${item.queueId}:${action}`;
                          return (
                            <button
                              className="inline-action"
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
              </tbody>
            </table>
          </div>
        ) : (
          <div className="action-queue-empty">
            <h3>No pending workflow actions</h3>
            <p>Dashboard endpoints did not return actionable alerts or recommendations.</p>
          </div>
        )}
      </section>
    </main>
  );
}
