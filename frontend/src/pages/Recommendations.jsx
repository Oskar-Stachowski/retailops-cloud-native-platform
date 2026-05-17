import { useCallback, useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import FeatureBoundary from "../components/FeatureBoundary";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import { getDashboardData } from "../services/retailopsApi";
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

  const type = humanizeToken(row.type, "Recommended action");
  const source = humanizeToken(row.source, "");

  return source ? `${type} (${source})` : type;
}

function productReference(row) {
  return <ProductReferenceCell row={row} />;
}

function productReferenceKey(row) {
  return firstPresent(row, ["sku", "product_sku", "product_id"], "na");
}

function statusWithDefault(row) {
  if (row.status || row.state) {
    return firstPresent(row, ["status", "state"]);
  }

  return row.source === "recommendation" ? "proposed" : "open";
}

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
    render: (row) => <StatusBadge status={statusWithDefault(row)} />,
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
    render: (row) => <StatusBadge status={statusWithDefault(row)} />,
  },
];

export default function Recommendations() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  const loadRecommendationContext = useCallback(async () => {
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

  if (state.loading) {
    return (
      <main className="api-page">
        <LoadingState title="Loading recommendation context" />
      </main>
    );
  }

  if (state.error) {
    return (
      <main className="api-page">
        <PageHeader
          eyebrow="Recommendation workflow"
          title="Recommendations"
          description="Current release exposes recommendation signals through Dashboard and Product 360 while the dedicated recommendation queue remains planned scope."
        />
        <ErrorState message={state.error.message} onRetry={loadRecommendationContext} />
      </main>
    );
  }

  const summary = state.data?.summary || {};
  const recommendations = state.data?.recommendations || [];
  const openWorkItems = state.data?.openWorkItems || [];
  const alerts = state.data?.alerts || [];

  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Recommendation workflow"
        title="Recommendations"
        description="Decision-support view built from existing backend recommendation and work-item signals. The dedicated approval queue is positioned as planned workflow maturity, not as a visual placeholder."
      />

      <section className="metrics-grid" aria-label="Recommendation context metrics">
        <MetricCard
          label="Recommendations"
          value={recommendations.length || summary.recommendationCount || 0}
          helper="Suggested actions from dashboard API"
          tone="neutral"
        />
        <MetricCard
          label="Open work items"
          value={openWorkItems.length || summary.openWorkItems || 0}
          helper="Follow-up actions available today"
          status={openWorkItems.length ? "Open" : "Clear"}
          tone={openWorkItems.length ? "warning" : "success"}
        />
        <MetricCard
          label="Related alerts"
          value={alerts.length || summary.openAlerts || 0}
          helper="Signals that may trigger recommendations"
          status={alerts.length ? "Watch" : "Clear"}
          tone={alerts.length ? "warning" : "success"}
        />
        <MetricCard
          label="Approval queue"
          value="Planned"
          helper="Future accept/reject/escalate workflow"
        />
      </section>

      <FeatureBoundary
        eyebrow="Release boundary"
        title="Current release exposes recommendations through decision-support views"
        currentScope="Recommendations are already visible as operational guidance from Dashboard and Product 360 workflows. A dedicated queue for approval, escalation and audit is planned as workflow maturity."
        availableSignals={[
          "Dashboard recommendations from the live FastAPI dashboard endpoint",
          "Open work items for operational follow-up",
          "Related alerts that explain why a recommendation exists",
        ]}
        futureScope="Add a dedicated recommendation queue with lifecycle states, owner assignment, decisions and audit evidence."
        plannedSteps={[
          "Add accepted, rejected, escalated and pending recommendation states",
          "Connect recommendations to Action Queue decisions",
          "Add decision history and business-impact tracking",
        ]}
      />

      <DataTable
        title="Available recommendation signals"
        description="Current recommendation evidence is loaded from backend-backed dashboard data, not from local placeholder rows."
        columns={recommendationColumns}
        rows={recommendations.slice(0, 10)}
        getRowKey={(row) =>
          row.id ||
          row.recommendation_id ||
          `${productReferenceKey(row)}:${signalLabel(row)}`
        }
        emptyMessage="No recommendations were returned by the current dashboard endpoint. Dedicated queue records remain planned scope."
      />

      <DataTable
        title="Related open work items"
        description="Work items connect suggested actions with operational follow-up until the dedicated approval queue is implemented."
        columns={workItemColumns}
        rows={openWorkItems.slice(0, 10)}
        getRowKey={(row) => row.id || `${row.source || "work"}:${signalLabel(row)}`}
        emptyMessage="No open work items were returned by the dashboard endpoint."
      />
    </main>
  );
}
