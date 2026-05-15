export function resolveRowKey(row, getRowKey) {
  if (typeof getRowKey === "function") {
    const key = getRowKey(row);

    if (key !== undefined && key !== null && key !== "") {
      return String(key);
    }
  }

  if (row?.id !== undefined && row?.id !== null && row.id !== "") {
    return String(row.id);
  }

  throw new Error("DataTable rows require an 'id' field or a getRowKey prop.");
}
