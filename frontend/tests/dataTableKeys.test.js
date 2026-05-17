import test from "node:test";
import assert from "node:assert/strict";
import { resolveRowKey } from "../src/components/dataTableKeys.js";

test("resolveRowKey uses explicit getRowKey when provided", () => {
  const rowKey = resolveRowKey(
    { sku: "SKU-1", updated_at: "2026-05-13T12:00:00Z" },
    (row) => `${row.sku}:${row.updated_at}`,
  );

  assert.equal(rowKey, "SKU-1:2026-05-13T12:00:00Z");
});

test("resolveRowKey falls back to row.id", () => {
  assert.equal(resolveRowKey({ id: "ROW-1", sku: "SKU-1" }), "ROW-1");
});

test("resolveRowKey throws when row.id and getRowKey are both missing", () => {
  assert.throws(
    () => resolveRowKey({ sku: "SKU-1" }),
    /DataTable rows require an 'id' field or a getRowKey prop\./,
  );
});
