export default function FeatureBoundary({
  title = "Implementation boundary",
  currentScope,
  futureScope,
  eyebrow = "Scope boundary",
}) {
  return (
    <section className="feature-boundary">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{currentScope}</p>
      <div className="feature-boundary__next">
        <strong>Future implementation:</strong>
        <span>{futureScope}</span>
      </div>
    </section>
  );
}
