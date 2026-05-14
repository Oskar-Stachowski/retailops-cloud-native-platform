import FeatureBoundary from "../components/FeatureBoundary";
import PageHeader from "../components/PageHeader";
import "../styles/api-connected-ui.css";

export default function Anomalies() {
  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Anomaly monitoring"
        title="Anomalies"
        description="Investigation view for unusual operational signals. The page keeps the same layout shell as the production-ready views while the dedicated anomalies API remains future scope."
      />

      <FeatureBoundary
        title="Dedicated anomaly API is future scope"
        currentScope="CS-016 removes frontend mocks. Because the current repository tree does not show a dedicated anomalies API router, this page intentionally does not render fake anomaly rows."
        futureScope="Add a backend /anomalies endpoint, connect this page to real anomaly records, then add filters by SKU, severity, type and investigation status."
      />
    </main>
  );
}
