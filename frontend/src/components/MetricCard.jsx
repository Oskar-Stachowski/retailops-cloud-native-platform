const TONE_ALIASES = {
  positive: "success",
  risk: "danger",
};

function normalizeTone(tone) {
  return TONE_ALIASES[tone] || tone || "neutral";
}

export default function MetricCard({ label, value, helper, status, tone = "neutral" }) {
  const displayValue = value === null || value === undefined || value === "" ? "—" : value;
  const normalizedTone = normalizeTone(tone);

  return (
    <article className={`metric-card metric-card--${normalizedTone}`}>
      <div className="metric-card__topline">
        <span className="metric-card__label">{label}</span>
        {status ? <span className="metric-card__badge">{status}</span> : null}
      </div>
      <strong className="metric-card__value">{displayValue}</strong>
      {helper ? <span className="metric-card__helper">{helper}</span> : null}
    </article>
  );
}
