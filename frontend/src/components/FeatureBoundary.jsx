export default function FeatureBoundary({ title, currentScope, futureScope }) {
  return (
    <section className="feature-boundary">
      <p className="eyebrow">CS-016 scope boundary</p>
      <h1>{title}</h1>
      <p>{currentScope}</p>
      <div className="feature-boundary__next">
        <strong>Future implementation:</strong>
        <span>{futureScope}</span>
      </div>
    </section>
  );
}
