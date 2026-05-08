import logging

import pytest

from app.db.instrumentation import (
    classify_statement,
    instrument_database_call,
    render_database_metrics,
)


def test_classify_statement_normalizes_common_sql_verbs() -> None:
    assert classify_statement(" SELECT * FROM products") == "select"
    assert classify_statement("insert into products values (1)") == "insert"
    assert classify_statement("UPDATE products SET name = 'x'") == "update"
    assert classify_statement("delete from products") == "delete"
    assert classify_statement("") == "unknown"
    assert classify_statement("WITH recent AS (SELECT 1) SELECT * FROM recent") == "other"


def test_instrument_database_call_logs_structured_operation(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.db")

    result = instrument_database_call(
        operation="fetch_all",
        query="SELECT * FROM products",
        callback=lambda: [{"id": "product-1"}],
        row_count=len,
    )

    assert result == [{"id": "product-1"}]
    record = caplog.records[-1]
    assert record.message == "Database operation completed"
    assert record.db_operation == "fetch_all"
    assert record.db_statement_type == "select"
    assert record.db_status == "success"
    assert record.db_row_count == 1


def test_instrument_database_call_records_error_metrics() -> None:
    with pytest.raises(RuntimeError):
        instrument_database_call(
            operation="fetch_one",
            query="SELECT * FROM products",
            callback=lambda: (_ for _ in ()).throw(RuntimeError("db failed")),
        )

    metrics = render_database_metrics()

    assert "retailops_db_operations_total" in metrics
    assert 'operation="fetch_one",statement_type="select",status="error"' in metrics
