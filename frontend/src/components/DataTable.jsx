import { isValidElement } from "react";
import EmptyState from "./EmptyState";
import { IdentifierText } from "./tableCells.jsx";
import { isTechnicalIdentifier } from "./tableCellFormatters.js";
import { resolveRowKey } from "./dataTableKeys.js";

function getCellValue(row, column) {
  if (typeof column.accessor === "function") {
    return column.accessor(row);
  }

  return row?.[column.accessor];
}

function formatCellValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (isValidElement(value)) {
    return value;
  }

  if (isTechnicalIdentifier(value)) {
    return <IdentifierText value={value} />;
  }

  return value;
}

export default function DataTable({
  title,
  description,
  columns,
  rows,
  emptyMessage,
  getRowKey,
}) {
  if (!rows?.length) {
    return <EmptyState title={title || "No records"} message={emptyMessage} />;
  }

  return (
    <section className="table-card">
      {title || description ? (
        <header className="table-card__header">
          {title ? <h2>{title}</h2> : null}
          {description ? <p>{description}</p> : null}
        </header>
      ) : null}
      <div className="table-card__scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key || column.header}>{column.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={resolveRowKey(row, getRowKey)}>
                {columns.map((column) => (
                  <td key={column.key || column.header}>
                    {formatCellValue(column.render ? column.render(row) : getCellValue(row, column))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
