import { useCallback, useEffect, useMemo, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import { InsightVisualCard, MiniBarList } from "../components/MiniVisualizations";
import PageHeader from "../components/PageHeader";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import { getForecasts } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

const FORECAST_BUSINESS_USES = [
  {
    title: "Inventory planning",
    description: "Plan expected stock needs before the next forecast period starts.",
  },
  {
    title: "Replenishment",
    description: "Prioritize products that need purchase orders or warehouse transfers.",
  },
  {
    title: "Demand signal",
    description: "Feed stock-risk and workflow recommendation views with baseline demand.",
  },
];

function numberValue(value) {
  const parsedValue = Number(value);

  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function confidenceFraction(row) {
  const rawConfidence = numberValue(
    row.confidence_level ?? row.confidence ?? row.confidence_score,
  );

  if (rawConfidence === null) {
    return null;
  }

  return Math.max(0, Math.min(rawConfidence <= 1 ? rawConfidence : rawConfidence / 100, 1));
}

function formatPercent(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }

  return `${Math.round(value * 100)}%`;
}

function confidenceTone(confidence) {
  if (confidence === null || confidence === undefined) {
    return "unknown";
  }

  if (confidence >= 0.8) {
    return "strong";
  }

  if (confidence >= 0.65) {
    return "moderate";
  }

  return "weak";
}

function confidenceLabel(confidence) {
  const tone = confidenceTone(confidence);

  if (tone === "strong") {
    return "Strong";
  }

  if (tone === "moderate") {
    return "Moderate";
  }

  if (tone === "weak") {
    return "Review";
  }

  return "Missing";
}

function averageConfidence(rows) {
  const confidenceValues = (rows || [])
    .map((row) => confidenceFraction(row))
    .filter((value) => value !== null);

  if (!confidenceValues.length) {
    return null;
  }

  const total = confidenceValues.reduce((sum, value) => sum + value, 0);
  return total / confidenceValues.length;
}

function productIdentity(row, index) {
  return (
    row.sku ||
    row.product_sku ||
    row.product_name ||
    row.name ||
    row.product_id ||
    `Forecast ${index + 1}`
  );
}

function forecastConfidenceItems(rows) {
  return (rows || []).slice(0, 8).map((row, index) => {
    const confidence = confidenceFraction(row) ?? 0;

    return {
      label: productIdentity(row, index),
      value: Math.round(confidence * 100),
      valueLabel: formatPercent(confidence),
    };
  });
}

function countUniqueProducts(rows) {
  return new Set(
    rows
      .map((row) => row.product_id || row.sku || row.product_sku || row.product_name)
      .filter(Boolean),
  ).size;
}

function forecastMethodLabel(rows) {
  const method = rows.find((row) => row.method)?.method;

  if (!method) {
    return "baseline demand model";
  }

  return String(method).replace(/[-_]+/g, " ");
}

function ConfidenceIndicator({ confidence, label = "Confidence" }) {
  const tone = confidenceTone(confidence);
  const width = confidence === null || confidence === undefined ? 0 : Math.round(confidence * 100);

  return (
    <div className={`confidence-indicator confidence-indicator--${tone}`}>
      <div className="confidence-indicator__topline">
        <span>{label}</span>
        <strong>{formatPercent(confidence)}</strong>
      </div>
      <div
        className="confidence-indicator__track"
        aria-label={`${label}: ${formatPercent(confidence)}`}
      >
        <span style={{ width: `${width}%` }} />
      </div>
      <small>{confidenceLabel(confidence)}</small>
    </div>
  );
}

function ConfidenceCell({ row }) {
  const confidence = confidenceFraction(row);

  return <ConfidenceIndicator confidence={confidence} label="Row confidence" />;
}

function ForecastPlanningInsight({ rows }) {
  const coveredProducts = countUniqueProducts(rows);
  const confidence = averageConfidence(rows);
  const method = forecastMethodLabel(rows);
  const productLabel = coveredProducts === 1 ? "product" : "products";

  return (
    <section className="planning-insight-panel">
      <div className="planning-insight-panel__summary">
        <p className="eyebrow">Planning insight</p>
        <h2>
          {coveredProducts} {productLabel} covered by {method}.
        </h2>
        <p>
          Average confidence: {formatPercent(confidence)}. Forecasts are used by stock-risk and
          workflow recommendation views to turn demand signals into operational actions.
        </p>
      </div>

      <ConfidenceIndicator confidence={confidence} label="Average confidence" />

      <div className="planning-use-grid" aria-label="Forecast business uses">
        {FORECAST_BUSINESS_USES.map((item) => (
          <article key={item.title}>
            <strong>{item.title}</strong>
            <span>{item.description}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

const columns = [
  {
    header: "Product",
    render: (row) => <ProductReferenceCell row={row} nameKeys={["product_name", "name"]} />,
  },
  {
    header: "Period start",
    accessor: (row) =>
      row.forecast_period_start || row.forecast_date || row.date || "—",
  },
  {
    header: "Period end",
    accessor: (row) => row.forecast_period_end || "—",
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
    render: (row) => <ConfidenceCell row={row} />,
  },
  {
    header: "Business use",
    accessor: () => "Inventory planning · Replenishment · Demand signal",
  },
  {
    header: "Method",
    accessor: (row) =>
      row.method || row.model_version || row.model_name || "baseline",
  },
  {
    header: "Generated",
    accessor: (row) => row.generated_at || row.created_at || "—",
  },
];

export default function Forecasts() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    forecasts: [],
  });

  useEffect(() => {
    let isMounted = true;

    async function loadInitialForecasts() {
      try {
        const forecasts = await getForecasts({
          sortBy: "generated_at",
          sortOrder: "desc",
        });

        if (isMounted) {
          setState({
            loading: false,
            error: null,
            forecasts,
          });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            loading: false,
            error,
            forecasts: [],
          });
        }
      }
    }

    loadInitialForecasts();

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
      const forecasts = await getForecasts({
        sortBy: "generated_at",
        sortOrder: "desc",
      });

      setState({
        loading: false,
        error: null,
        forecasts,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        forecasts: [],
      });
    }
  }, []);

  const planningSummary = useMemo(
    () => ({
      coveredProducts: countUniqueProducts(state.forecasts),
      averageConfidence: averageConfidence(state.forecasts),
      method: forecastMethodLabel(state.forecasts),
    }),
    [state.forecasts],
  );

  if (state.loading) {
    return (
      <main className="api-page">
        <LoadingState title="Loading forecasts" />
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

  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Forecasts API"
        title="Demand forecast foundation"
        description="Forecast records are loaded from the backend `/forecasts` endpoint and explain how baseline demand signals support inventory planning, replenishment and workflow recommendations."
      />

      <section className="metrics-grid">
        <MetricCard
          label="Forecast coverage"
          value={planningSummary.coveredProducts}
          helper="Products covered by baseline demand model"
          status={`${state.forecasts.length} rows`}
          tone="success"
        />
        <MetricCard
          label="Average confidence"
          value={formatPercent(planningSummary.averageConfidence)}
          helper="Mean confidence across returned forecast rows"
          tone={confidenceTone(planningSummary.averageConfidence) === "weak" ? "warning" : "neutral"}
        />
        <MetricCard
          label="Confidence signal"
          value={confidenceLabel(planningSummary.averageConfidence)}
          helper="Mini indicator below shows planning readiness"
          tone={confidenceTone(planningSummary.averageConfidence) === "strong" ? "success" : "warning"}
        />
        <MetricCard
          label="Planning uses"
          value={FORECAST_BUSINESS_USES.length}
          helper="Inventory planning, replenishment and demand signal"
          tone="neutral"
        />
      </section>

      <ForecastPlanningInsight rows={state.forecasts} />

      <section className="mini-visual-grid mini-visual-grid--two">
        <InsightVisualCard
          eyebrow="Forecast confidence"
          title="Per-product confidence scan"
          description="A quick planning scan of confidence by SKU or product name for the latest forecast rows."
        >
          <MiniBarList
            items={forecastConfidenceItems(state.forecasts)}
            emptyMessage="Forecast rows do not expose confidence values yet."
          />
        </InsightVisualCard>
      </section>

      <DataTable
        title="Backend forecast records"
        description="Forecast rows now include product identity and planning context, not only technical product IDs."
        columns={columns}
        rows={state.forecasts}
        getRowKey={(row) => row.id || `${row.product_id || row.sku || "na"}:${row.forecast_period_start || row.forecast_date || row.date || "na"}`}
        emptyMessage="The backend returned no forecasts. Check seed data and /forecasts API response."
      />
    </main>
  );
}
