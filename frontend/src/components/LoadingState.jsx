export default function LoadingState({ title = "Loading data", message = "Fetching live data from backend API..." }) {
  return (
    <section className="state-card state-card--loading" role="status" aria-live="polite">
      <div className="state-card__spinner" aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
    </section>
  );
}
