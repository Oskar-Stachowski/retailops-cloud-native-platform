function toFiniteNumber(value) {
  const numberValue = Number(value);

  return Number.isFinite(numberValue) ? numberValue : null;
}

function formatCompactNumber(value) {
  const numberValue = toFiniteNumber(value);

  if (numberValue === null) {
    return "—";
  }

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: numberValue >= 100 ? 0 : 1,
    notation: Math.abs(numberValue) >= 10000 ? "compact" : "standard",
  }).format(numberValue);
}

function normalizePercent(value, maxValue) {
  const numberValue = Math.max(0, toFiniteNumber(value) ?? 0);
  const maxNumber = Math.max(1, toFiniteNumber(maxValue) ?? 1);

  return Math.min(100, Math.round((numberValue / maxNumber) * 100));
}

function EmptyVisual({ message }) {
  return <p className="mini-visual-empty">{message}</p>;
}

export function InsightVisualCard({ eyebrow, title, description, children }) {
  return (
    <article className="mini-visual-card">
      <header className="mini-visual-card__header">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h3>{title}</h3>
        {description ? <p>{description}</p> : null}
      </header>
      {children}
    </article>
  );
}

export function LineSparkChart({
  rows,
  valueAccessor,
  labelAccessor,
  valueFormatter = formatCompactNumber,
  emptyMessage = "No trend points available.",
}) {
  const points = (rows || [])
    .map((row, index) => ({
      label: labelAccessor ? labelAccessor(row, index) : String(index + 1),
      value: toFiniteNumber(valueAccessor ? valueAccessor(row, index) : row?.value),
    }))
    .filter((point) => point.value !== null);

  if (!points.length) {
    return <EmptyVisual message={emptyMessage} />;
  }

  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const spread = maxValue - minValue || Math.max(1, Math.abs(maxValue));
  const width = 320;
  const height = 96;
  const padding = 12;
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const coordinates = points.map((point, index) => {
    const x = points.length === 1
      ? width / 2
      : padding + (index / (points.length - 1)) * usableWidth;
    const y = padding + ((maxValue - point.value) / spread) * usableHeight;

    return { ...point, x, y };
  });
  const polylinePoints = coordinates
    .map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
  const firstPoint = coordinates[0];
  const lastPoint = coordinates[coordinates.length - 1];
  const areaPoints = [
    `${firstPoint.x.toFixed(2)},${height - padding}`,
    polylinePoints,
    `${lastPoint.x.toFixed(2)},${height - padding}`,
  ].join(" ");
  const delta = (lastPoint.value ?? 0) - (firstPoint.value ?? 0);

  return (
    <div className="line-spark-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Trend from ${valueFormatter(firstPoint.value)} to ${valueFormatter(lastPoint.value)}`}
      >
        <polygon className="line-spark-chart__area" points={areaPoints} />
        <polyline className="line-spark-chart__line" points={polylinePoints} />
        {coordinates.map((point) => (
          <circle
            className="line-spark-chart__point"
            cx={point.x}
            cy={point.y}
            key={`${point.label}:${point.x}`}
            r="3"
          />
        ))}
      </svg>
      <footer className="line-spark-chart__footer">
        <span>{firstPoint.label}</span>
        <strong>{valueFormatter(lastPoint.value)}</strong>
        <span>{points.length > 1 ? lastPoint.label : "single point"}</span>
      </footer>
      <p className="mini-visual-note">
        {delta >= 0 ? "+" : ""}
        {valueFormatter(delta)} vs first point
      </p>
    </div>
  );
}

export function DistributionBars({
  items,
  emptyMessage = "No distribution data available.",
}) {
  const visibleItems = (items || [])
    .map((item) => ({
      ...item,
      value: Math.max(0, toFiniteNumber(item.value) ?? 0),
    }))
    .filter((item) => item.label && item.value > 0);
  const maxValue = Math.max(...visibleItems.map((item) => item.value), 0);

  if (!visibleItems.length || maxValue <= 0) {
    return <EmptyVisual message={emptyMessage} />;
  }

  return (
    <div className="distribution-bars">
      {visibleItems.map((item, index) => (
        <div className="distribution-bars__row" key={`${item.label}:${index}`}>
          <div className="distribution-bars__label">
            <span>{item.label}</span>
            <strong>{formatCompactNumber(item.value)}</strong>
          </div>
          <div
            className="distribution-bars__track"
            role="img"
            aria-label={`${item.label}: ${formatCompactNumber(item.value)}`}
          >
            <span style={{ width: `${normalizePercent(item.value, maxValue)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function MiniBarList({
  items,
  emptyMessage = "No bar data available.",
}) {
  const visibleItems = (items || [])
    .map((item) => ({
      ...item,
      value: Math.max(0, toFiniteNumber(item.value) ?? 0),
    }))
    .filter((item) => item.label && item.value > 0);
  const maxValue = Math.max(...visibleItems.map((item) => item.value), 0);

  if (!visibleItems.length || maxValue <= 0) {
    return <EmptyVisual message={emptyMessage} />;
  }

  return (
    <div className="mini-bar-list">
      {visibleItems.map((item, index) => (
        <div className="mini-bar-list__item" key={`${item.label}:${index}`}>
          <div className="mini-bar-list__topline">
            <span>{item.label}</span>
            <strong>{item.valueLabel || formatCompactNumber(item.value)}</strong>
          </div>
          <div className="mini-bar-list__track">
            <span style={{ width: `${normalizePercent(item.value, maxValue)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
