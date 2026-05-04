export default function MetricCard({ label, value, helper, tone = "neutral" }) {
  const displayValue = value === null || value === undefined || value === "" ? "—" : value;

  return (
    <article className={`metric-card metric-card--${tone}`}>
      <span className="metric-card__label">{label}</span>
      <strong className="metric-card__value">{displayValue}</strong>
      {helper ? <span className="metric-card__helper">{helper}</span> : null}
    </article>
  );
}
