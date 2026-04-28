const anomalySignals = [
  {
    title: "Sales Drop",
    icon: "🔻",
    status: "Planned",
    description:
      "Detect unusual product-level demand drops that may require commercial or operational action.",
  },
  {
    title: "Inventory Spike",
    icon: "📦",
    status: "Planned",
    description:
      "Highlight abnormal inventory movements, potential overstock and stock data inconsistencies.",
  },
  {
    title: "Pricing Outlier",
    icon: "💸",
    status: "Planned",
    description:
      "Prepare the UI area for future price, margin and promotion anomaly signals.",
  },
  {
    title: "Data Quality Alert",
    icon: "🧪",
    status: "Planned",
    description:
      "Expose suspicious data events before they affect dashboards, forecasts or recommendations.",
  },
];

function Anomalies() {
  return (
    <section className="modules" id="anomalies">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">!</span>
        <div>
          <p className="eyebrow">Operational signals</p>
          <h2>Anomalies</h2>
        </div>
      </div>

      <div className="module-grid">
        {anomalySignals.map((signal) => (
          <article className="module-card module-pink" key={signal.title}>
            <div className="module-icon" aria-hidden="true">{signal.icon}</div>
            <h3>{signal.title}</h3>
            <p>{signal.description}</p>
            <span>{signal.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Anomalies;
