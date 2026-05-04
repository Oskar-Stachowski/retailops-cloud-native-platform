export default function StatusBadge({ status, children }) {
  const normalizedStatus = String(status || "unknown").toLowerCase().replace(/\s+/g, "_");

  return (
    <span className={`status-badge status-badge--${normalizedStatus}`}>
      {children || normalizedStatus.replace(/_/g, " ")}
    </span>
  );
}
