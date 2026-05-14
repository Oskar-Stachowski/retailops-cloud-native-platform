import { useCallback, useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import { InsightVisualCard, MiniBarList } from "../components/MiniVisualizations";
import PageHeader from "../components/PageHeader";
import { ProductReferenceCell } from "../components/tableCells.jsx";
import { getForecasts } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

const columns = [
  {
    header: "Product",
    render: (row) => <ProductReferenceCell row={row} />,
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
    accessor: (row) => {
      const confidence = row.confidence_level ?? row.confidence ?? row.confidence_score;

      if (confidence === undefined || confidence === null) {
        return "—";
      }

      const normalizedConfidence = confidence <= 1 ? confidence * 100 : confidence;

      return `${Math.round(normalizedConfidence)}%`;
    },
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

function numberValue(value) {
  const parsedValue = Number(value);

  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function forecastConfidenceItems(rows) {
  return (rows || []).slice(0, 8).map((row, index) => {
    const rawConfidence = numberValue(
      row.confidence_level ?? row.confidence ?? row.confidence_score,
    ) ?? 0;
    const confidence = rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence;
    const label =
      row.sku || row.product_sku || row.product_name || row.product_id || `Forecast ${index + 1}`;

    return {
      label,
      value: Math.round(confidence),
      valueLabel: `${Math.round(confidence)}%`,
    };
  });
}

function countUniqueProducts(rows) {
  return new Set(
    rows
      .map((row) => row.product_id || row.sku || row.product_sku)
      .filter(Boolean),
  ).size;
}

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
        const forecasts = await getForecasts();

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
      const forecasts = await getForecasts();

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
        description="Forecast records are loaded from the backend `/forecasts` endpoint and support inventory planning evidence."
      />

      <section className="metrics-grid">
        <MetricCard
          label="Forecast rows"
          value={state.forecasts.length}
          helper="Rows returned by backend"
        />
        <MetricCard
          label="Covered products"
          value={countUniqueProducts(state.forecasts)}
          helper="Unique products with forecasts"
          tone="neutral"
        />
      </section>


      <section className="mini-visual-grid mini-visual-grid--two">
        <InsightVisualCard
          eyebrow="Forecast confidence"
          title="Latest confidence mini bars"
          description="A quick scan of model confidence for the most recent forecast rows."
        >
          <MiniBarList
            items={forecastConfidenceItems(state.forecasts)}
            emptyMessage="Forecast rows do not expose confidence values yet."
          />
        </InsightVisualCard>
      </section>

      <DataTable
        title="Backend forecast records"
        description="This is a baseline view. Forecast accuracy charts and model evaluation remain future scope."
        columns={columns}
        rows={state.forecasts}
        getRowKey={(row) => row.id || `${row.product_id || row.sku || "na"}:${row.forecast_period_start || row.forecast_date || row.date || "na"}`}
        emptyMessage="The backend returned no forecasts. Check seed data and /forecasts API response."
      />
    </main>
  );
}
