from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from threading import Lock
import time
from typing import Any, Callable, TypeVar


logger = logging.getLogger("app.db")
T = TypeVar("T")


@dataclass
class DatabaseOperationStats:
    count: int = 0
    duration_seconds_sum: float = 0.0
    duration_seconds_max: float = 0.0


_stats: dict[tuple[str, str, str], DatabaseOperationStats] = defaultdict(
    DatabaseOperationStats,
)
_stats_lock = Lock()


def classify_statement(query: Any) -> str:
    text = str(query).strip()
    if not text:
        return "unknown"

    first_token = text.split(maxsplit=1)[0].lower()
    if first_token in {"select", "insert", "update", "delete"}:
        return first_token

    return "other"


def observe_database_operation(
    *,
    operation: str,
    statement_type: str,
    status: str,
    duration_seconds: float,
    row_count: int | None = None,
) -> None:
    key = (operation, statement_type, status)
    with _stats_lock:
        stats = _stats[key]
        stats.count += 1
        stats.duration_seconds_sum += duration_seconds
        stats.duration_seconds_max = max(
            stats.duration_seconds_max,
            duration_seconds,
        )

    logger.info(
        "Database operation completed",
        extra={
            "db_operation": operation,
            "db_statement_type": statement_type,
            "db_status": status,
            "db_duration_ms": round(duration_seconds * 1000, 2),
            "db_row_count": row_count,
        },
    )


def instrument_database_call(
    *,
    operation: str,
    query: Any,
    callback: Callable[[], T],
    row_count: Callable[[T], int | None] | None = None,
) -> T:
    statement_type = classify_statement(query)
    started_at = time.perf_counter()

    try:
        result = callback()
    except Exception:
        observe_database_operation(
            operation=operation,
            statement_type=statement_type,
            status="error",
            duration_seconds=time.perf_counter() - started_at,
        )
        raise

    observe_database_operation(
        operation=operation,
        statement_type=statement_type,
        status="success",
        duration_seconds=time.perf_counter() - started_at,
        row_count=row_count(result) if row_count else None,
    )
    return result


def render_database_metrics() -> str:
    with _stats_lock:
        snapshot = list(_stats.items())

    lines = [
        "# HELP retailops_db_operations_total Total database operations by operation, statement type and status.",
        "# TYPE retailops_db_operations_total counter",
    ]
    for labels, stats in snapshot:
        operation, statement_type, status = labels
        lines.append(
            "retailops_db_operations_total"
            f'{{operation="{operation}",statement_type="{statement_type}",status="{status}"}} '
            f"{stats.count}"
        )

    lines.extend(
        [
            "# HELP retailops_db_operation_duration_seconds_sum Cumulative database operation duration in seconds.",
            "# TYPE retailops_db_operation_duration_seconds_sum counter",
        ]
    )
    for labels, stats in snapshot:
        operation, statement_type, status = labels
        lines.append(
            "retailops_db_operation_duration_seconds_sum"
            f'{{operation="{operation}",statement_type="{statement_type}",status="{status}"}} '
            f"{stats.duration_seconds_sum:.6f}"
        )

    lines.extend(
        [
            "# HELP retailops_db_operation_duration_seconds_max Maximum observed database operation duration in seconds.",
            "# TYPE retailops_db_operation_duration_seconds_max gauge",
        ]
    )
    for labels, stats in snapshot:
        operation, statement_type, status = labels
        lines.append(
            "retailops_db_operation_duration_seconds_max"
            f'{{operation="{operation}",statement_type="{statement_type}",status="{status}"}} '
            f"{stats.duration_seconds_max:.6f}"
        )

    return "\n".join(lines)
