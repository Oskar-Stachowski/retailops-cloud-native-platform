export default function EmptyState({ title = "No data available", message }) {
  return (
    <section className="state-card state-card--empty">
      <h2>{title}</h2>
      <p>{message || "The backend returned an empty dataset for this view."}</p>
    </section>
  );
}
