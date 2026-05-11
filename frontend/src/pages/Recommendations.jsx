import FeatureBoundary from "../components/FeatureBoundary";
import "../styles/api-connected-ui.css";

export default function Recommendations() {
  return (
    <main className="api-page">
      <FeatureBoundary
        title="Recommendations"
        currentScope="Recommendations are available from dashboard and Product 360 workflows; this route is reserved for a dedicated recommendations queue."
        futureScope="Add /recommendations and workflow-action endpoints, then display real accepted, rejected, escalated and pending recommendations."
      />
    </main>
  );
}
