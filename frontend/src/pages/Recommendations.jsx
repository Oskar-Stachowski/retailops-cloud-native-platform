import FeatureBoundary from "../components/FeatureBoundary";
import "../styles/api-connected-ui.css";

export default function Recommendations() {
  return (
    <main className="api-page">
      <FeatureBoundary
        title="Recommendations"
        currentScope="CS-016 removes local mock recommendations. This page is kept as a navigation placeholder until a real recommendations API is implemented."
        futureScope="Add /recommendations and workflow-action endpoints, then display real accepted, rejected, escalated and pending recommendations."
      />
    </main>
  );
}
