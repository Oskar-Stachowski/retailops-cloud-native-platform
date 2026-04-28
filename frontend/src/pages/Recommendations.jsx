const recommendationAreas = [
  {
    title: "Action Queue",
    icon: "✅",
    status: "Planned",
    description:
      "Future place for prioritized business actions generated from inventory, forecast and anomaly signals.",
  },
  {
    title: "Decision Evidence",
    icon: "📌",
    status: "Planned",
    description:
      "Show why a recommendation exists, which signals support it and what decision it helps with.",
  },
  {
    title: "Owner Assignment",
    icon: "👥",
    status: "Planned",
    description:
      "Prepare the UI for assigning recommendations to category, inventory or operations owners.",
  },
  {
    title: "Business Impact",
    icon: "🎯",
    status: "Planned",
    description:
      "Reserve space for future estimated impact, confidence and execution status.",
  },
];

function Recommendations() {
  return (
    <section className="modules" id="recommendations">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">★</span>
        <div>
          <p className="eyebrow">Decision support</p>
          <h2>Recommendations</h2>
        </div>
      </div>

      <div className="module-grid">
        {recommendationAreas.map((area) => (
          <article className="module-card module-green" key={area.title}>
            <div className="module-icon" aria-hidden="true">{area.icon}</div>
            <h3>{area.title}</h3>
            <p>{area.description}</p>
            <span>{area.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Recommendations;
