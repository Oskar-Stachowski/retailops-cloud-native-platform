"""Summarize verified RF variants on shared fixed-origin forecast rows."""

# ruff: noqa: INP001 - standalone CLI script

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from ml.evaluation.metrics import calculate_forecast_metrics
from ml.experiments.assessed_run import AssessedRun, load_assessed_run
from ml.features.demand_forecast import observation_known_at_origin

SAMPLE_COLUMNS = (
    "split",
    "origin",
    "forecast_date",
    "horizon_day",
    "category",
    "product_id",
    "store_id",
    "channel",
    "actual_units",
    "predicted_units",
    "baseline_predicted_units",
    "seasonal_predicted_units",
)


def _prediction_key(row: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        str(row[field])
        for field in ("split", "origin", "forecast_date", "product_id", "store_id", "channel")
    )


def _fold_summary(run: AssessedRun) -> list[dict[str, object]]:
    return [
        {
            "split": fold["split"],
            "origin": fold["origin"],
            "target_start": fold["target_start"],
            "target_end": fold["target_end"],
            "eligible_rows": fold["eligible_rows"],
            "evaluated_rows": fold["evaluated_rows"],
            "coverage": fold["coverage"],
            "rf": fold["model_metrics"],
            "moving_average": fold["baseline_metrics"],
        }
        for fold in run.metrics["temporal_protocol"]["folds"]
    ]


def _run_summary(run: AssessedRun) -> dict[str, object]:
    return {
        "experiment_id": run.metrics["experiment_id"],
        "run_id": run.metrics["run_id"],
        "model_id": run.metrics["model_id"],
        "feature_dataset_id": run.metrics["feature_dataset_id"],
        "n_estimators": run.metrics["n_estimators"],
        "status": run.metrics["model_status"],
        "admission_checks": {
            check["check_id"]: check["status"]
            for check in run.metrics["admission_decision"]["checks"]
        },
        "validation_mean_wape": str(
            sum(
                Decimal(str(fold["model_metrics"]["wape"]))
                for fold in run.metrics["temporal_protocol"]["folds"]
                if str(fold["split"]).startswith("validation_")
            )
            / Decimal(3)
        ),
        "folds": _fold_summary(run),
        "predictions_logical_sha256": run.manifest["predictions_logical_sha256"],
        "run_manifest_sha256": run.manifest_sha256,
        "environment": run.inputs["environment"],
        "source_tree_sha256": run.inputs["source"]["source_tree_sha256"],
        "source_git_commit": run.inputs["source"]["git_commit"],
        "source_worktree_changes": run.inputs["source"]["source_worktree_changes"],
    }


def _inputs_without_command(run: AssessedRun) -> dict[str, object]:
    return {key: value for key, value in run.inputs.items() if key != "reproduction_command"}


def _metrics_without_run_fields(run: AssessedRun) -> dict[str, object]:
    return {
        key: value
        for key, value in run.metrics.items()
        if key not in {"experiment_id", "run_id", "generated_at"}
    }


def _seasonal_rows(run: AssessedRun) -> list[dict[str, object]]:
    panel = {
        (str(row["date"]), str(row["product_id"]), str(row["store_id"]), str(row["channel"])): row
        for row in run.panel
    }
    output = []
    for prediction in run.predictions:
        target = date.fromisoformat(str(prediction["forecast_date"]))
        origin = date.fromisoformat(str(prediction["origin"])[:10]) + timedelta(days=1)
        target_row = panel[(target.isoformat(), *(_prediction_key(prediction)[3:]))]
        lag = panel.get(
            ((target - timedelta(days=7)).isoformat(), *(_prediction_key(prediction)[3:])),
        )
        if lag is None or lag["units_sold"] is None or not observation_known_at_origin(lag, origin):
            continue
        output.append(
            {
                **prediction,
                "category": target_row["category"],
                "seasonal_predicted_units": int(lag["units_sold"]),
            }
        )
    return output


def _three_way_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "rows": len(rows),
        "rf": calculate_forecast_metrics(rows, prediction_field="predicted_units"),
        "moving_average": calculate_forecast_metrics(
            rows, prediction_field="baseline_predicted_units"
        ),
        "seasonal_naive_7_day": calculate_forecast_metrics(
            rows, prediction_field="seasonal_predicted_units"
        ),
    }


def _comparison(run: AssessedRun) -> tuple[dict[str, object], list[dict[str, object]]]:
    seasonal = _seasonal_rows(run)
    by_split: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in seasonal:
        by_split[str(row["split"])].append(row)
    fold_comparison = []
    for fold in run.metrics["temporal_protocol"]["folds"]:
        split = str(fold["split"])
        rows = by_split[split]
        fold_comparison.append(
            {
                "split": split,
                "seasonal_eligible_rows": len(rows),
                "evaluated_rows": fold["evaluated_rows"],
                "same_row_comparison": _three_way_metrics(rows),
            }
        )
    final = by_split["test"]
    segments = {}
    for field in ("category", "store_id", "channel"):
        values: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in final:
            values[str(row[field])].append(row)
        segments[field] = {
            value: _three_way_metrics(rows) for value, rows in sorted(values.items())
        }
    return {"folds": fold_comparison, "test_segments": segments}, final


def build_report(
    run_20: AssessedRun,
    run_80: AssessedRun,
    repeat_80: AssessedRun,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    runs = (run_20, run_80, repeat_80)
    if len({run.metrics["feature_dataset_id"] for run in runs}) != 1:
        msg = "Variants use different feature datasets."
        raise ValueError(msg)
    if len({run.inputs["source"]["source_tree_sha256"] for run in runs}) != 1:
        msg = "Variants use different source trees."
        raise ValueError(msg)
    if len({json.dumps(run.inputs["environment"], sort_keys=True) for run in runs}) != 1:
        msg = "Variants use different dependency environments."
        raise ValueError(msg)
    if [_prediction_key(row) for row in run_20.predictions] != [
        _prediction_key(row) for row in run_80.predictions
    ]:
        msg = "Variants were not evaluated on the same forecast rows."
        raise ValueError(msg)
    if [row["actual_units"] for row in run_20.predictions] != [
        row["actual_units"] for row in run_80.predictions
    ]:
        msg = "Variants disagree on actual demand."
        raise ValueError(msg)
    if [row["baseline_predicted_units"] for row in run_20.predictions] != [
        row["baseline_predicted_units"] for row in run_80.predictions
    ]:
        msg = "Variants disagree on moving-average predictions."
        raise ValueError(msg)
    if run_20.metrics["n_estimators"] != 20 or run_80.metrics["n_estimators"] != 80:
        msg = "Unexpected estimator counts."
        raise ValueError(msg)
    if (
        _inputs_without_command(run_80) != _inputs_without_command(repeat_80)
        or _metrics_without_run_fields(run_80) != _metrics_without_run_fields(repeat_80)
        or run_80.metrics["model_id"] != repeat_80.metrics["model_id"]
        or run_80.manifest["predictions_logical_sha256"]
        != repeat_80.manifest["predictions_logical_sha256"]
    ):
        msg = "The selected variant did not reproduce exactly."
        raise ValueError(msg)
    summaries = {"rf_20": _run_summary(run_20), "rf_80": _run_summary(run_80)}
    selected = min(
        summaries,
        key=lambda label: (Decimal(summaries[label]["validation_mean_wape"]), label),
    )
    selected_run = {"rf_20": run_20, "rf_80": run_80}[selected]
    comparison, final = _comparison(selected_run)
    return {
        "selection_rule": "Lower mean WAPE across three validation windows; final test excluded.",
        "selected_variant": selected,
        "variants": summaries,
        "reproduction": {
            "run_id": repeat_80.metrics["run_id"],
            "experiment_id": repeat_80.metrics["experiment_id"],
            "model_id": repeat_80.metrics["model_id"],
            "predictions_logical_sha256": repeat_80.manifest["predictions_logical_sha256"],
            "inputs_equal_except_interpreter_path": True,
            "assessed_metrics_equal_except_run_identity_and_timestamp": True,
            "exact_integer_prediction_tolerance": 0,
            "matched": True,
        },
        "seasonal_comparison": comparison,
    }, final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-20", type=Path, required=True)
    parser.add_argument("--run-80", type=Path, required=True)
    parser.add_argument("--repeat-80", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, final = build_report(
        load_assessed_run(args.run_20),
        load_assessed_run(args.run_80),
        load_assessed_run(args.repeat_80),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "analysis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sample = []
    for horizon_day in range(1, 8):
        sample.extend(
            sorted(
                (row for row in final if int(row["horizon_day"]) == horizon_day),
                key=lambda row: (
                    str(row["category"]),
                    str(row["product_id"]),
                    str(row["store_id"]),
                ),
            )[:3]
        )
    with (args.output_dir / "predictions_sample.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=SAMPLE_COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(sample)


if __name__ == "__main__":
    main()
