const forecastCards = [
  {
    title: "Demand Forecast",
    icon: "📈",
    status: "Planned",
    description:
      "Future dashboard area for product-level and category-level demand forecasts.",
  },
  {
    title: "Forecast Inputs",
    icon: "🧾",
    status: "Planned",
    description:
      "Placeholder for historical sales, inventory, seasonality and promotion input signals.",
  },
  {
    title: "Model Evidence",
    icon: "🧠",
    status: "Planned",
    description:
      "Space for future forecast quality indicators, model version and monitoring status.",
  },
  {
    title: "Planning Support",
    icon: "🗓️",
    status: "Planned",
    description:
      "Translate forecast outputs into planning evidence for inventory and commercial teams.",
  },
];

function Forecasts() {
  return (
    <section className="modules" id="forecasts">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">◇</span>
        <div>
          <p className="eyebrow">ML-ready dashboard area</p>
          <h2>Forecasts</h2>
        </div>
      </div>

      <div className="module-grid">
        {forecastCards.map((card) => (
          <article className="module-card module-purple" key={card.title}>
            <div className="module-icon" aria-hidden="true">{card.icon}</div>
            <h3>{card.title}</h3>
            <p>{card.description}</p>
            <span>{card.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Forecasts;
