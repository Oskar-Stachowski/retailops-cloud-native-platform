const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HEX_ID_PATTERN = /^[0-9a-f]{24,}$/i;

export function isTechnicalIdentifier(value) {
  if (typeof value !== "string") {
    return false;
  }

  const normalized = value.trim();

  return UUID_PATTERN.test(normalized) || HEX_ID_PATTERN.test(normalized);
}
