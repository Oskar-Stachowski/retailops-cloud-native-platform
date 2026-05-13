from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.connection import fetch_all, fetch_one, get_connection
from app.domain.models import ForecastRun

if TYPE_CHECKING:
    from uuid import UUID


class ForecastRunRepository:
    """Persistence layer for model/forecast pipeline run metadata."""

    SORT_COLUMNS: ClassVar[dict[str, str]] = {
        "completed_at": "completed_at",
        "started_at": "started_at",
        "model_version": "model_version",
        "status": "status",
        "created_at": "created_at",
    }

    def __init__(self, connection: object | None = None) -> None:
        self.connection = connection

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        if self.connection is None:
            return fetch_one(query, params)

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        if self.connection is None:
            return fetch_all(query, params)

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _execute_one(
        self,
        query: str,
        params: tuple[Any, ...],
    ) -> dict[str, Any]:
        if self.connection is None:
            with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
            return dict(row)

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        self.connection.commit()
        return dict(row)

    def _map_row_to_forecast_run(self, row: dict[str, Any]) -> ForecastRun:
        return ForecastRun(
            id=row["id"],
            run_key=row["run_key"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            model_type=row["model_type"],
            status=row["status"],
            profile=row["profile"],
            seed=row["seed"],
            feature_dataset_name=row["feature_dataset_name"],
            feature_dataset_id=row["feature_dataset_id"],
            feature_grain=row["feature_grain"],
            target=row["target"],
            window_days=row["window_days"],
            horizon_days=row["horizon_days"],
            holdout_days=row["holdout_days"],
            feature_row_count=row["feature_row_count"],
            forecast_row_count=row["forecast_row_count"],
            evaluated_rows=row["evaluated_rows"],
            skipped_rows=row["skipped_rows"],
            metrics=row["metrics"],
            artifacts=row["artifacts"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _build_filters(
        self,
        status: str | None,
        model_version: str | None,
        feature_dataset_id: str | None,
    ) -> tuple[str, list[Any]]:
        filters = []
        params: list[Any] = []

        if status:
            filters.append("status = %s")
            params.append(status.strip())

        if model_version:
            filters.append("model_version = %s")
            params.append(model_version.strip())

        if feature_dataset_id:
            filters.append("feature_dataset_id = %s")
            params.append(feature_dataset_id.strip())

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params

    def upsert_forecast_run(self, forecast_run: ForecastRun) -> ForecastRun:
        row = self._execute_one(
            """
            INSERT INTO forecast_runs (
                id,
                run_key,
                model_name,
                model_version,
                model_type,
                status,
                profile,
                seed,
                feature_dataset_name,
                feature_dataset_id,
                feature_grain,
                target,
                window_days,
                horizon_days,
                holdout_days,
                feature_row_count,
                forecast_row_count,
                evaluated_rows,
                skipped_rows,
                metrics,
                artifacts,
                started_at,
                completed_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_key)
            DO UPDATE SET
                model_name = EXCLUDED.model_name,
                model_version = EXCLUDED.model_version,
                model_type = EXCLUDED.model_type,
                status = EXCLUDED.status,
                profile = EXCLUDED.profile,
                seed = EXCLUDED.seed,
                feature_dataset_name = EXCLUDED.feature_dataset_name,
                feature_dataset_id = EXCLUDED.feature_dataset_id,
                feature_grain = EXCLUDED.feature_grain,
                target = EXCLUDED.target,
                window_days = EXCLUDED.window_days,
                horizon_days = EXCLUDED.horizon_days,
                holdout_days = EXCLUDED.holdout_days,
                feature_row_count = EXCLUDED.feature_row_count,
                forecast_row_count = EXCLUDED.forecast_row_count,
                evaluated_rows = EXCLUDED.evaluated_rows,
                skipped_rows = EXCLUDED.skipped_rows,
                metrics = EXCLUDED.metrics,
                artifacts = EXCLUDED.artifacts,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                updated_at = now()
            RETURNING
                id,
                run_key,
                model_name,
                model_version,
                model_type,
                status,
                profile,
                seed,
                feature_dataset_name,
                feature_dataset_id,
                feature_grain,
                target,
                window_days,
                horizon_days,
                holdout_days,
                feature_row_count,
                forecast_row_count,
                evaluated_rows,
                skipped_rows,
                metrics,
                artifacts,
                started_at,
                completed_at,
                created_at,
                updated_at;
            """,
            (
                forecast_run.id,
                forecast_run.run_key,
                forecast_run.model_name,
                forecast_run.model_version,
                forecast_run.model_type,
                forecast_run.status.value,
                forecast_run.profile,
                forecast_run.seed,
                forecast_run.feature_dataset_name,
                forecast_run.feature_dataset_id,
                Jsonb(forecast_run.feature_grain),
                forecast_run.target,
                forecast_run.window_days,
                forecast_run.horizon_days,
                forecast_run.holdout_days,
                forecast_run.feature_row_count,
                forecast_run.forecast_row_count,
                forecast_run.evaluated_rows,
                forecast_run.skipped_rows,
                Jsonb(forecast_run.metrics),
                Jsonb(forecast_run.artifacts),
                forecast_run.started_at,
                forecast_run.completed_at,
            ),
        )
        return self._map_row_to_forecast_run(row)

    def get_forecast_run_by_id(self, forecast_run_id: UUID) -> ForecastRun | None:
        row = self._fetch_one(
            self._select_query("WHERE id = %s"),
            (forecast_run_id,),
        )
        return self._map_row_to_forecast_run(row) if row else None

    def get_forecast_run_by_key(self, run_key: str) -> ForecastRun | None:
        row = self._fetch_one(
            self._select_query("WHERE run_key = %s"),
            (run_key,),
        )
        return self._map_row_to_forecast_run(row) if row else None

    def list_forecast_runs(
        self,
        *,
        status: str | None = None,
        model_version: str | None = None,
        feature_dataset_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "completed_at",
        sort_order: str = "desc",
    ) -> list[ForecastRun]:
        where_clause, params = self._build_filters(
            status=status,
            model_version=model_version,
            feature_dataset_id=feature_dataset_id,
        )
        sort_column = self.SORT_COLUMNS.get(sort_by, "completed_at")
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"
        rows = self._fetch_all(
            self._select_query(
                f"{where_clause} ORDER BY {sort_column} {direction}, created_at DESC LIMIT %s OFFSET %s",
            ),
            (*params, limit, offset),
        )
        return [self._map_row_to_forecast_run(row) for row in rows]

    def count_forecast_runs(
        self,
        *,
        status: str | None = None,
        model_version: str | None = None,
        feature_dataset_id: str | None = None,
    ) -> int:
        where_clause, params = self._build_filters(
            status=status,
            model_version=model_version,
            feature_dataset_id=feature_dataset_id,
        )
        row = self._fetch_one(
            f"SELECT COUNT(*) AS total FROM forecast_runs {where_clause};",  # noqa: S608 - where clause is built from fixed filters
            tuple(params),
        )
        return int(row["total"]) if row else 0

    def _select_query(self, suffix: str) -> str:
        return f"""
            SELECT
                id,
                run_key,
                model_name,
                model_version,
                model_type,
                status,
                profile,
                seed,
                feature_dataset_name,
                feature_dataset_id,
                feature_grain,
                target,
                window_days,
                horizon_days,
                holdout_days,
                feature_row_count,
                forecast_row_count,
                evaluated_rows,
                skipped_rows,
                metrics,
                artifacts,
                started_at,
                completed_at,
                created_at,
                updated_at
            FROM forecast_runs
            {suffix};
        """
