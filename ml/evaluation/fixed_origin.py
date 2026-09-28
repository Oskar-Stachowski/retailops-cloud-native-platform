"""Bounded, fixed-origin evaluation on an explicit synthetic daily panel."""

from __future__ import annotations

import argparse
import csv
import json
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from data.generator.common import BASE_DATE
from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.profile_engine import profile_defaults
from ml.evaluation.metrics import calculate_forecast_metrics
from ml.experiments.identity import logical_rows_sha256
from ml.features.demand_forecast import (
    build_demand_feature_rows,
    forecast_origin_utc,
    observation_at_origin,
)
from ml.features.observation_history import append_version, history_json, observation_at_time
from ml.models.random_forest_forecast import (
    MODEL_VERSION,
    build_random_forest_pipeline,
    build_training_features,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sklearn.pipeline import Pipeline

REPORT_FILENAME = "fixed_origin_report.json"
PREDICTIONS_FILENAME = "fixed_origin_predictions.csv"
PANEL_FILENAME = "daily_panel.csv"
PROTOCOL_VERSION = "synthetic_fixed_origin_v1"
PANEL_EVIDENCE = "synthetic_profile_completeness_assumption_v1"
PanelKey = tuple[str, str, str, str]
SeriesKey = tuple[str, str, str]
SCORABLE = {"observed_zero", "observed_positive", "complete_zero"}
PREDICTION_COLUMNS = [
    "split",
    "origin",
    "forecast_date",
    "horizon_day",
    "product_id",
    "store_id",
    "channel",
    "actual_units",
    "predicted_units",
    "baseline_predicted_units",
]
PANEL_COLUMNS = [
    "date",
    "product_id",
    "store_id",
    "channel",
    "category",
    "brand",
    "day_of_week",
    "is_weekend",
    "week_of_year",
    "month",
    "is_active_assortment",
    "location_open",
    "source_data_complete",
    "source_evidence_available_at",
    "units_sold",
    "observation_status",
    "observation_available_at",
    "observation_history",
]


@dataclass(frozen=True)
class DailyEvidence:
    assortment_active: bool | None
    location_open: bool | None
    source_complete: bool | None
    available_at: datetime | None


@dataclass(frozen=True)
class FixedOriginConfig:
    dataset: DatasetGenerationConfig = field(
        default_factory=lambda: DatasetGenerationConfig(profile="small"),
    )
    horizon_days: int = 7
    window_days: int = 28
    min_history_observations: int = 7
    validation_windows: int = 3
    n_estimators: int = 20
    random_state: int = 42
    max_panel_rows: int = 100_000
    output_dir: Path | None = None


def _day(value: object) -> date:
    return date.fromisoformat(str(value))


def _series_key(row: dict[str, object]) -> SeriesKey:
    return (str(row["product_id"]), str(row["store_id"]), str(row["channel"]))


def _label_known(row: dict[str, object], origin: date) -> bool:
    return observation_at_time(row, forecast_origin_utc(origin)) is not None


def _calendar(date_value: date) -> dict[str, object]:
    return {
        "day_of_week": date_value.isoweekday(),
        "is_weekend": date_value.isoweekday() in {6, 7},
        "week_of_year": date_value.isocalendar().week,
        "month": date_value.month,
    }


def _synthetic_evidence(
    day: date,
    product: dict[str, str],
    store: dict[str, str],
) -> DailyEvidence:
    return DailyEvidence(
        assortment_active=product["status"] == "active",
        location_open=store["status"] == "active",
        source_complete=True,
        available_at=forecast_origin_utc(day + timedelta(days=1)),
    )


def _panel_status(evidence: DailyEvidence, sale: dict[str, object] | None) -> str:
    if evidence.assortment_active is False:
        return "inactive_assortment"
    if evidence.location_open is False:
        return "location_closed"
    if evidence.assortment_active is None or evidence.location_open is None:
        return "unknown_eligibility"
    if evidence.source_complete is not True or evidence.available_at is None:
        return "missing_data"
    return str(sale["observation_status"]) if sale is not None else "complete_zero"


def build_daily_panel(
    feature_rows: list[dict[str, object]],
    products: list[dict[str, str]],
    stores: list[dict[str, str]],
    *,
    date_start: date,
    date_end: date,
    max_panel_rows: int,
    assume_synthetic_complete: bool = False,
    evidence_overrides: Mapping[PanelKey, DailyEvidence] | None = None,
) -> list[dict[str, object]]:
    """Build every series/day; absent evidence never implies a zero."""
    if date_end < date_start:
        msg = "date_end must not precede date_start."
        raise ValueError(msg)
    day_count = (date_end - date_start).days + 1
    if day_count * len(products) * len(stores) > max_panel_rows:
        msg = "Daily panel exceeds max_panel_rows; use a bounded profile."
        raise ValueError(msg)
    sale_by_key: dict[PanelKey, dict[str, object]] = {}
    for row in feature_rows:
        key = (str(row["date"]), *_series_key(row))
        if key in sale_by_key:
            msg = f"Duplicate sale grain: {key}"
            raise ValueError(msg)
        sale_by_key[key] = row
    overrides = evidence_overrides or {}
    panel: list[dict[str, object]] = []
    for day_offset in range(day_count):
        current_day = date_start + timedelta(days=day_offset)
        date_text = current_day.isoformat()
        for product in products:
            for store in stores:
                key = (date_text, product["id"], store["id"], store["channel"])
                evidence = overrides.get(key)
                if evidence is None:
                    evidence = (
                        _synthetic_evidence(current_day, product, store)
                        if assume_synthetic_complete
                        else DailyEvidence(None, None, None, None)
                    )
                sale = sale_by_key.get(key)
                status = _panel_status(evidence, sale)
                if sale is not None and status in {"inactive_assortment", "location_closed"}:
                    msg = f"Sale conflicts with eligibility evidence: {key}"
                    raise ValueError(msg)
                available_at = evidence.available_at
                if sale is not None and available_at is not None:
                    sale_available = datetime.fromisoformat(str(sale["observation_available_at"]))
                    available_at = max(available_at, sale_available)
                quantity_history = sale.get("observation_history") if sale is not None else None
                if quantity_history is None:
                    quantity_history = history_json(
                        append_version(
                            [],
                            int(sale["units_sold"]) if sale is not None else 0,
                            available_at.isoformat(),
                        )
                        if available_at is not None and status in SCORABLE
                        else []
                    )
                panel.append(
                    {
                        "date": date_text,
                        "product_id": product["id"],
                        "store_id": store["id"],
                        "channel": store["channel"],
                        "category": product["category"],
                        "brand": product["brand"],
                        **_calendar(current_day),
                        "is_active_assortment": evidence.assortment_active,
                        "location_open": evidence.location_open,
                        "source_data_complete": evidence.source_complete,
                        "source_evidence_available_at": (
                            evidence.available_at.isoformat() if evidence.available_at else ""
                        ),
                        "units_sold": (int(sale["units_sold"]) if sale is not None else 0)
                        if status in SCORABLE
                        else None,
                        "observation_status": status,
                        "observation_available_at": available_at.isoformat()
                        if available_at
                        else "",
                        "observation_history": quantity_history,
                    },
                )
    unexpected = set(sale_by_key) - {(str(row["date"]), *_series_key(row)) for row in panel}
    if unexpected:
        msg = f"Sales outside declared panel: {len(unexpected)}"
        raise ValueError(msg)
    return panel


def chronological_windows(
    date_start: date,
    date_end: date,
    *,
    horizon_days: int,
    validation_windows: int,
    min_history_observations: int,
) -> list[tuple[str, date]]:
    if min(horizon_days, validation_windows, min_history_observations) <= 0:
        msg = "Horizon, validation count and minimum history must be positive."
        raise ValueError(msg)
    final_origin = date_end - timedelta(days=horizon_days - 1)
    first_origin = final_origin - timedelta(days=validation_windows * horizon_days)
    earliest_training_origin = date_start + timedelta(days=min_history_observations)
    if earliest_training_origin + timedelta(days=horizon_days) > first_origin:
        msg = "Not enough calendar days for training, validation and final test."
        raise ValueError(msg)
    return [
        (
            "test" if index == validation_windows else f"validation_{index + 1}",
            first_origin + timedelta(days=index * horizon_days),
        )
        for index in range(validation_windows + 1)
    ]


def _history(
    rows: list[dict[str, object]],
    origin: date,
    window_days: int,
) -> list[dict[str, object]]:
    window_start = origin - timedelta(days=window_days)
    return [
        known
        for row in rows
        if _day(row["date"]) >= window_start
        and (known := observation_at_origin(row, origin)) is not None
    ]


def _training_examples(
    rows_by_series: dict[SeriesKey, list[dict[str, object]]],
    *,
    date_start: date,
    fold_origin: date,
    config: FixedOriginConfig,
) -> tuple[list[dict[str, object]], list[int]]:
    features: list[dict[str, object]] = []
    labels: list[int] = []
    origin = date_start + timedelta(days=config.min_history_observations)
    last_training_origin = fold_origin - timedelta(days=config.horizon_days)
    while origin <= last_training_origin:
        target_end = origin + timedelta(days=config.horizon_days)
        for series_rows in rows_by_series.values():
            history = _history(series_rows, origin, config.window_days)
            if len(history) < config.min_history_observations:
                continue
            for target in series_rows:
                target_date = _day(target["date"])
                if not (origin <= target_date < target_end):
                    continue
                if target["observation_status"] not in SCORABLE or not _label_known(
                    target,
                    fold_origin,
                ):
                    continue
                label = observation_at_time(target, forecast_origin_utc(fold_origin))
                if label["observation_status"] not in SCORABLE:
                    continue
                features.append(
                    build_training_features(
                        target,
                        history,
                        window_days=config.window_days,
                        origin=origin,
                    ),
                )
                labels.append(int(label["units_sold"]))
        origin += timedelta(days=config.horizon_days)
    return features, labels


def _metric(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _metrics(predictions: list[dict[str, object]], prediction_field: str) -> dict[str, object]:
    return calculate_forecast_metrics(predictions, prediction_field=prediction_field)


def evaluate_fixed_origin(  # noqa: PLR0912 - explicit fold eligibility and coverage branches
    panel: list[dict[str, object]],
    *,
    date_start: date,
    date_end: date,
    config: FixedOriginConfig,
) -> tuple[dict[str, object], list[dict[str, object]], Pipeline]:
    windows = chronological_windows(
        date_start,
        date_end,
        horizon_days=config.horizon_days,
        validation_windows=config.validation_windows,
        min_history_observations=config.min_history_observations,
    )
    rows_by_series: dict[SeriesKey, list[dict[str, object]]] = defaultdict(list)
    for row in panel:
        rows_by_series[_series_key(row)].append(row)
    for series_rows in rows_by_series.values():
        series_rows.sort(key=lambda row: str(row["date"]))
    all_predictions: list[dict[str, object]] = []
    fold_reports: list[dict[str, object]] = []
    final_model: Pipeline | None = None
    for split, origin in windows:
        train_features, train_labels = _training_examples(
            rows_by_series,
            date_start=date_start,
            fold_origin=origin,
            config=config,
        )
        if not train_features:
            msg = f"No training examples before {origin}."
            raise ValueError(msg)
        model = build_random_forest_pipeline(
            n_estimators=config.n_estimators,
            random_state=config.random_state,
        )
        model.fit(train_features, train_labels)
        if split == "test":
            final_model = model
        candidates: list[tuple[dict[str, object], dict[str, object], int]] = []
        skipped: Counter[str] = Counter()
        eligible_rows = 0
        target_end = origin + timedelta(days=config.horizon_days)
        for series_rows in rows_by_series.values():
            history = _history(series_rows, origin, config.window_days)
            for target in series_rows:
                target_date = _day(target["date"])
                if not (origin <= target_date < target_end):
                    continue
                status = str(target["observation_status"])
                if status in {"inactive_assortment", "location_closed"}:
                    skipped[status] += 1
                    continue
                eligible_rows += 1
                if status not in SCORABLE:
                    skipped[status] += 1
                    continue
                if len(history) < config.min_history_observations:
                    skipped["insufficient_history"] += 1
                    continue
                baseline = sum(Decimal(str(row["units_sold"])) for row in history) / Decimal(
                    len(history),
                )
                baseline_units = max(
                    0,
                    int(baseline.quantize(Decimal(1), rounding=ROUND_HALF_UP)),
                )
                candidates.append(
                    (
                        target,
                        build_training_features(
                            target,
                            history,
                            window_days=config.window_days,
                            origin=origin,
                        ),
                        baseline_units,
                    ),
                )
        predictions = (
            model.predict([features for _, features, _ in candidates]) if candidates else []
        )
        fold_predictions: list[dict[str, object]] = []
        for (target, _, baseline_units), predicted in zip(candidates, predictions, strict=True):
            target_date = _day(target["date"])
            fold_predictions.append(
                {
                    "split": split,
                    "origin": forecast_origin_utc(origin).isoformat(),
                    "forecast_date": target_date.isoformat(),
                    "horizon_day": (target_date - origin).days + 1,
                    "product_id": target["product_id"],
                    "store_id": target["store_id"],
                    "channel": target["channel"],
                    "actual_units": target["units_sold"],
                    "predicted_units": max(
                        0, int(Decimal(str(predicted)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                    ),
                    "baseline_predicted_units": baseline_units,
                },
            )
        all_predictions.extend(fold_predictions)
        fold_reports.append(
            {
                "split": split,
                "origin": forecast_origin_utc(origin).isoformat(),
                "target_start": origin.isoformat(),
                "target_end": (target_end - timedelta(days=1)).isoformat(),
                "training_examples": len(train_features),
                "panel_rows": len(rows_by_series) * config.horizon_days,
                "eligible_rows": eligible_rows,
                "evaluated_rows": len(fold_predictions),
                "coverage": _metric(Decimal(len(fold_predictions)) / Decimal(eligible_rows))
                if eligible_rows
                else None,
                "skipped": dict(sorted(skipped.items())),
                "model_metrics": _metrics(fold_predictions, "predicted_units"),
                "baseline_metrics": _metrics(fold_predictions, "baseline_predicted_units"),
            },
        )
    if final_model is None:
        msg = "Final test model was not trained."
        raise RuntimeError(msg)
    return (
        {
            "protocol_version": PROTOCOL_VERSION,
            "source_evidence": PANEL_EVIDENCE,
            "model_version": MODEL_VERSION,
            "business_timezone": "UTC",
            "origin_rule": "previous_day_23_59_59_utc",
            "horizon_days": config.horizon_days,
            "window_days": config.window_days,
            "min_history_observations": config.min_history_observations,
            "validation_windows": config.validation_windows,
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "panel_rows": len(panel),
            "panel_status_counts": dict(
                sorted(Counter(str(row["observation_status"]) for row in panel).items())
            ),
            "folds": fold_reports,
            "final_test_split": "test",
            "test_used_for_selection": False,
        },
        all_predictions,
        final_model,
    )


def default_output_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "ci-cd"
        / "reports"
        / "ml"
        / "fixed-origin"
        / uuid.uuid4().hex
    )


def run_fixed_origin_evaluation(config: FixedOriginConfig) -> dict[str, object]:
    if config.dataset.profile == "demo":
        msg = "The demo fixture has no complete daily source declaration."
        raise ValueError(msg)
    defaults = profile_defaults(config.dataset.profile)
    days = config.dataset.days or defaults.days
    products = config.dataset.products or defaults.products
    stores = config.dataset.stores or defaults.stores
    if days * products * stores > config.max_panel_rows:
        msg = "Daily panel exceeds max_panel_rows; use a bounded profile."
        raise ValueError(msg)
    tables = build_dataset(config.dataset)
    feature_rows = build_demand_feature_rows(tables, config.dataset)
    date_start = BASE_DATE - timedelta(days=days - 1)
    panel = build_daily_panel(
        feature_rows,
        tables["products"],
        tables["stores"],
        date_start=date_start,
        date_end=BASE_DATE,
        max_panel_rows=config.max_panel_rows,
        assume_synthetic_complete=True,
    )
    report, predictions, _ = evaluate_fixed_origin(
        panel,
        date_start=date_start,
        date_end=BASE_DATE,
        config=config,
    )
    report["dataset_id"] = str(feature_rows[0]["dataset_id"]) if feature_rows else ""
    report["profile"] = config.dataset.profile
    report["seed"] = config.dataset.seed
    report["n_estimators"] = config.n_estimators
    report["random_state"] = config.random_state
    report["requested_dataset_config"] = asdict(config.dataset)
    report["effective_dataset_size"] = {"days": days, "products": products, "stores": stores}
    report["panel_logical_sha256"] = logical_rows_sha256(panel)
    output_dir = config.output_dir or default_output_dir()
    if output_dir.exists() and any(output_dir.iterdir()):
        msg = f"Output directory is not empty: {output_dir}"
        raise FileExistsError(msg)
    report["output_dir"] = str(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / PANEL_FILENAME).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PANEL_COLUMNS)
        writer.writeheader()
        writer.writerows(panel)
    (output_dir / REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / PREDICTIONS_FILENAME).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PREDICTION_COLUMNS)
        writer.writeheader()
        writer.writerows(predictions)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic demand forecasts at fixed origins."
    )
    parser.add_argument("--profile", choices=("small", "medium", "large"), default="small")
    parser.add_argument("--days", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--stores", type=int)
    parser.add_argument("--warehouses", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon-days", type=int, default=7)
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument("--min-history-observations", type=int, default=7)
    parser.add_argument("--validation-windows", type=int, default=3)
    parser.add_argument("--n-estimators", type=int, default=20)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = FixedOriginConfig(
        dataset=DatasetGenerationConfig(
            profile=args.profile,
            days=args.days,
            products=args.products,
            stores=args.stores,
            warehouses=args.warehouses,
            seed=args.seed,
        ),
        horizon_days=args.horizon_days,
        window_days=args.window_days,
        min_history_observations=args.min_history_observations,
        validation_windows=args.validation_windows,
        n_estimators=args.n_estimators,
        output_dir=args.output_dir,
    )
    report = run_fixed_origin_evaluation(config)
    print(  # noqa: T201 - CLI output
        f"Fixed-origin evaluation: {report['panel_rows']} panel rows; output: {report['output_dir']}"
    )


if __name__ == "__main__":
    main()
