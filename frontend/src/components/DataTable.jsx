import EmptyState from "./EmptyState";

function getCellValue(row, column) {
  if (typeof column.accessor === "function") {
    return column.accessor(row);
  }

  return row?.[column.accessor];
}

function formatCellValue(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export default function DataTable({ title, description, columns, rows, emptyMessage }) {
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
            {rows.map((row, index) => (
              <tr key={row.id || row.product_id || row.sku || index}>
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
