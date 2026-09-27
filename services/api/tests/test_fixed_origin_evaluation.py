from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from data.generator.common import BASE_DATE
from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.evaluation.fixed_origin import (
    PREDICTIONS_FILENAME,
    REPORT_FILENAME,
    DailyEvidence,
    FixedOriginConfig,
    build_daily_panel,
    evaluate_fixed_origin,
    run_fixed_origin_evaluation,
)
from ml.features.demand_forecast import build_demand_feature_rows, observation_known_at_origin
from ml.models.random_forest_forecast import build_training_features


def _fixture() -> tuple[FixedOriginConfig, dict[str, list[dict[str, str]]], list[dict[str, object]]]:
    config = FixedOriginConfig(
        dataset=DatasetGenerationConfig(
            profile="small", days=42, products=5, stores=2, warehouses=2, seed=42,
        ),
        n_estimators=8,
    )
    tables = build_dataset(config.dataset)
    features = build_demand_feature_rows(tables, config.dataset)
    return config, tables, features


def _panel(
    config: FixedOriginConfig,
    tables: dict[str, list[dict[str, str]]],
    features: list[dict[str, object]],
    overrides: dict[tuple[str, str, str, str], DailyEvidence] | None = None,
) -> list[dict[str, object]]:
    return build_daily_panel(
        features, tables["products"], tables["stores"],
        date_start=BASE_DATE - timedelta(days=41), date_end=BASE_DATE,
        max_panel_rows=config.max_panel_rows, assume_synthetic_complete=True,
        evidence_overrides=overrides,
    )


def test_panel_distinguishes_complete_zero_missing_closed_and_inactive() -> None:
    config, tables, features = _fixture()
    panel = _panel(config, tables, features)
    assert len(panel) == 42 * 5 * 2
    assert {row["observation_status"] for row in panel} == {
        "observed_positive", "complete_zero",
    }
    absent = [row for row in panel if row["observation_status"] == "complete_zero"][:4]
    assert len(absent) == 4
    statuses = ["missing_data", "location_closed", "inactive_assortment", "unknown_eligibility"]
    evidence = [
        DailyEvidence(True, True, False, datetime(2026, 5, 1, tzinfo=UTC)),
        DailyEvidence(True, False, True, datetime(2026, 5, 1, tzinfo=UTC)),
        DailyEvidence(False, True, True, datetime(2026, 5, 1, tzinfo=UTC)),
        DailyEvidence(None, True, True, datetime(2026, 5, 1, tzinfo=UTC)),
    ]
    overrides = {
        (str(row["date"]), str(row["product_id"]), str(row["store_id"]), str(row["channel"])): item
        for row, item in zip(absent, evidence, strict=True)
    }
    changed = _panel(config, tables, features, overrides)
    changed_by_key = {
        (str(row["date"]), str(row["product_id"]), str(row["store_id"]), str(row["channel"])): row
        for row in changed
    }
    for key, status in zip(overrides, statuses, strict=True):
        assert changed_by_key[key]["observation_status"] == status
        assert changed_by_key[key]["units_sold"] is None
    assert changed_by_key[next(iter(overrides))]["source_data_complete"] is False


def test_panel_without_completeness_evidence_never_invents_zero() -> None:
    config, tables, features = _fixture()

    panel = build_daily_panel(
        features, tables["products"], tables["stores"],
        date_start=BASE_DATE - timedelta(days=41), date_end=BASE_DATE,
        max_panel_rows=config.max_panel_rows,
    )

    assert {row["observation_status"] for row in panel} == {"unknown_eligibility"}
    assert all(row["units_sold"] is None for row in panel)
    assert all(row["source_data_complete"] is None for row in panel)


def test_calendar_lags_do_not_substitute_a_previous_observation_for_a_missing_day() -> None:
    config, tables, features = _fixture()
    panel = _panel(config, tables, features)
    series = sorted(
        [
            row for row in panel
            if all(row[field] == panel[0][field] for field in ("product_id", "store_id", "channel"))
        ],
        key=lambda row: str(row["date"]),
    )
    target = series[9]
    origin = date.fromisoformat(str(target["date"])) - timedelta(days=2)
    history = [series[5]]

    built = build_training_features(target, history, window_days=7, origin=origin)

    assert built["horizon_day"] == 3
    assert built["lag_1_available"] == 0
    assert built["lag_7_available"] == 0
    assert built["training_observation_count"] == 1


def test_origin_cutoff_excludes_late_fraction_of_previous_day() -> None:
    row = {"date": "2026-04-01", "observation_available_at": "2026-04-01T23:59:59Z"}
    assert observation_known_at_origin(row, date(2026, 4, 2))
    row["observation_available_at"] = "2026-04-01T23:59:59.500000Z"
    assert not observation_known_at_origin(row, date(2026, 4, 2))


def test_fixed_origin_report_has_three_validation_windows_and_untouched_test(tmp_path) -> None:
    config, _, _ = _fixture()
    config = FixedOriginConfig(dataset=config.dataset, n_estimators=8, output_dir=tmp_path)

    report = run_fixed_origin_evaluation(config)
    predictions = list(csv.DictReader((tmp_path / PREDICTIONS_FILENAME).open(encoding="utf-8")))
    written = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))

    assert report == written
    assert report["panel_rows"] == 420
    assert report["validation_windows"] == 3
    assert report["test_used_for_selection"] is False
    assert [fold["split"] for fold in report["folds"]] == [
        "validation_1", "validation_2", "validation_3", "test",
    ]
    assert all(fold["evaluated_rows"] == 70 for fold in report["folds"])
    assert all(fold["coverage"] == "1.0000" for fold in report["folds"])
    assert report["folds"][0]["origin"] == "2026-04-02T23:59:59+00:00"
    assert report["panel_status_counts"]["complete_zero"] > 0
    assert len(predictions) == 280
    assert {int(row["horizon_day"]) for row in predictions} == set(range(1, 8))
    assert all(row["origin"] == next(
        fold["origin"] for fold in report["folds"] if fold["split"] == row["split"]
    ) for row in predictions)
    for earlier, later in zip(report["folds"], report["folds"][1:], strict=False):
        assert earlier["target_end"] < later["target_start"]
    with pytest.raises(FileExistsError, match="not empty"):
        run_fixed_origin_evaluation(config)


def test_future_holdout_outcomes_cannot_change_frozen_predictions() -> None:
    config, tables, features = _fixture()
    panel = _panel(config, tables, features)
    start = BASE_DATE - timedelta(days=41)
    _, before, _ = evaluate_fixed_origin(panel, date_start=start, date_end=BASE_DATE, config=config)
    test_origin = BASE_DATE - timedelta(days=6)
    changed = [
        {**row, "units_sold": int(row["units_sold"]) + 1000}
        if date.fromisoformat(str(row["date"])) >= test_origin
        and row["observation_status"] == "observed_positive"
        else row
        for row in panel
    ]
    _, after, _ = evaluate_fixed_origin(changed, date_start=start, date_end=BASE_DATE, config=config)
    test_before = [row for row in before if row["split"] == "test"]
    test_after = [row for row in after if row["split"] == "test"]

    assert [row["actual_units"] for row in test_before] != [
        row["actual_units"] for row in test_after
    ]
    assert [
        (row["predicted_units"], row["baseline_predicted_units"])
        for row in test_before
    ] == [
        (row["predicted_units"], row["baseline_predicted_units"])
        for row in test_after
    ]


def test_report_counts_missing_data_and_insufficient_history() -> None:
    config, tables, features = _fixture()
    original = _panel(config, tables, features)
    key_series = tuple(str(original[0][field]) for field in ("product_id", "store_id", "channel"))
    first_origin = BASE_DATE - timedelta(days=27)
    overrides: dict[tuple[str, str, str, str], DailyEvidence] = {}
    for row in original:
        day = date.fromisoformat(str(row["date"]))
        if tuple(str(row[field]) for field in ("product_id", "store_id", "channel")) != key_series:
            continue
        if day < first_origin or day == BASE_DATE:
            overrides[(str(row["date"]), *key_series)] = DailyEvidence(
                True, True, False,
                datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            )
    panel = _panel(config, tables, features, overrides)

    report, _, _ = evaluate_fixed_origin(
        panel, date_start=BASE_DATE - timedelta(days=41), date_end=BASE_DATE, config=config,
    )

    first = report["folds"][0]
    final = report["folds"][-1]
    assert first["skipped"]["insufficient_history"] == 7
    assert first["evaluated_rows"] == 63
    assert final["skipped"]["missing_data"] == 1
    assert final["evaluated_rows"] == 69
    assert final["coverage"] == "0.9857"


def test_demo_without_completeness_evidence_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="no complete daily source declaration"):
        run_fixed_origin_evaluation(
            FixedOriginConfig(dataset=DatasetGenerationConfig(profile="demo"), output_dir=tmp_path),
        )
