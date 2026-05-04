import FeatureBoundary from "../components/FeatureBoundary";
import "../styles/api-connected-ui.css";

export default function Anomalies() {
  return (
    <main className="api-page">
      <FeatureBoundary
        title="Anomalies"
        currentScope="CS-016 removes frontend mocks. Because the current repository tree does not show a dedicated anomalies API router, this page intentionally does not render fake anomaly rows."
        futureScope="Add a backend /anomalies endpoint, connect this page to real anomaly records, then add filters by SKU, severity, type and investigation status."
      />
    </main>
  );
}
