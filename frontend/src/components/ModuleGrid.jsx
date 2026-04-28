function ModuleGrid({ modules }) {
  return (
    <section className="modules" id="modules">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">◇</span>
        <div>
          <p className="eyebrow">JSON-driven roadmap</p>
          <h2>Planned Dashboard Modules</h2>
        </div>
      </div>

      <div className="module-grid">
        {modules.map((dashboardModule) => (
          <article
            className={`module-card module-${dashboardModule.variant}`}
            key={dashboardModule.title}
          >
            <div className="module-icon" aria-hidden="true">
              {dashboardModule.icon}
            </div>
            <h3>{dashboardModule.title}</h3>
            <p>{dashboardModule.description}</p>
            <span>{dashboardModule.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

export default ModuleGrid;