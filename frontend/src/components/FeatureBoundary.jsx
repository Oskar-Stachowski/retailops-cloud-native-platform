export default function FeatureBoundary({
  title = "Implementation boundary",
  currentScope,
  availableSignals = [],
  futureScope,
  plannedSteps = [],
  eyebrow = "Scope boundary",
}) {
  return (
    <section className="feature-boundary">
      <div className="feature-boundary__intro">
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>

      <div className="feature-boundary__grid">
        <article className="feature-boundary__card">
          <span>Current scope</span>
          <p>{currentScope}</p>
        </article>

        <article className="feature-boundary__card">
          <span>Available signals</span>
          <ul>
            {availableSignals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </article>

        <article className="feature-boundary__card feature-boundary__card--planned">
          <span>Planned extension</span>
          <p>{futureScope}</p>
          {plannedSteps.length ? (
            <ul>
              {plannedSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          ) : null}
        </article>
      </div>
    </section>
  );
}
