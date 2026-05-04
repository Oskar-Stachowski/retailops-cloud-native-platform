export default function ErrorState({ title = "Backend data unavailable", message, onRetry }) {
  return (
    <section className="state-card state-card--error" role="alert">
      <div>
        <h2>{title}</h2>
        <p>{message || "The UI could not load data from the backend API."}</p>
      </div>
      {onRetry ? (
        <button className="secondary-button" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </section>
  );
}
