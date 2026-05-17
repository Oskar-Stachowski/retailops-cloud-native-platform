import { isTechnicalIdentifier } from "./tableCellFormatters.js";

function firstPresent(row, keys, fallback = "") {
  for (const key of keys) {
    const value = row?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return fallback;
}

function shortenIdentifier(value, head = 8, tail = 6) {
  if (value === undefined || value === null || value === "") {
    return "—";
  }

  const normalized = String(value).trim();

  if (!isTechnicalIdentifier(normalized)) {
    return normalized;
  }

  return `${normalized.slice(0, head)}...${normalized.slice(-tail)}`;
}

export function IdentifierText({ value, className = "" }) {
  if (value === undefined || value === null || value === "") {
    return "—";
  }

  const normalized = String(value).trim();
  const displayValue = shortenIdentifier(normalized);

  return (
    <span
      className={`identifier-text ${className}`.trim()}
      title={normalized}
      aria-label={normalized}
    >
      {displayValue}
    </span>
  );
}

export function ProductReferenceCell({
  row,
  idKeys = ["product_id", "productId"],
  nameKeys = ["product_name"],
}) {
  const sku = firstPresent(row, ["sku", "product_sku"]);
  const productName = firstPresent(row, nameKeys);
  const productId = firstPresent(row, idKeys);
  const primary = sku || productName || productId;
  const showProductName = sku && productName;
  const showProductId = productId && productId !== sku && productId !== productName;

  if (!primary) {
    return "—";
  }

  return (
    <span className="business-entity-cell" title={productId ? String(productId) : undefined}>
      <span className="business-entity-cell__primary">
        {isTechnicalIdentifier(String(primary)) ? (
          <IdentifierText value={primary} />
        ) : (
          primary
        )}
      </span>
      {showProductName || showProductId ? (
        <span className="business-entity-cell__secondary">
          {showProductName ? <span>{productName}</span> : null}
          {showProductId ? <IdentifierText value={productId} /> : null}
        </span>
      ) : null}
    </span>
  );
}
