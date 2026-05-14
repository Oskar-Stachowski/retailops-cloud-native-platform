import FeatureBoundary from "../components/FeatureBoundary";
import PageHeader from "../components/PageHeader";
import "../styles/api-connected-ui.css";

export default function Recommendations() {
  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Recommendation workflow"
        title="Recommendations"
        description="Decision-support route for recommended operational actions. Current recommendations are visible in Dashboard and Product 360, with a dedicated queue reserved for future implementation."
      />

      <FeatureBoundary
        title="Dedicated recommendations queue is future scope"
        currentScope="Recommendations are available from dashboard and Product 360 workflows; this route is reserved for a dedicated recommendations queue."
        futureScope="Add /recommendations and workflow-action endpoints, then display real accepted, rejected, escalated and pending recommendations."
      />
    </main>
  );
}
