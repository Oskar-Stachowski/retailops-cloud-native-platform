"""Frozen local admission checks for the synthetic Random Forest forecast."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path

from ml.evaluation.metrics import calculate_forecast_metrics

POLICY_PATH = Path(__file__).with_name("forecast_admission_v1.json")


def load_policy() -> tuple[dict[str, object], str]:
    raw = POLICY_PATH.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _number(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _check(
    check_id: str,
    status: str,
    value: object,
    threshold: object,
    sample_size: int,
    reason: str,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "status": status,
        "value": value,
        "threshold": threshold,
        "sample_size": sample_size,
        "reason": reason,
    }


def _protocol_check(
    report: dict[str, object],
    predictions: list[dict[str, object]],
    policy: dict[str, object],
) -> dict[str, object]:
    temporal = report.get("temporal_protocol")
    folds = temporal.get("folds") if isinstance(temporal, dict) else None
    expected_splits = [
        *(f"validation_{index + 1}" for index in range(policy["required_validation_windows"])),
        "test",
    ]
    valid = (
        report.get("evaluation_scope") == policy["evaluation_scope"]
        and isinstance(temporal, dict)
        and temporal.get("protocol_version") == policy["protocol_version"]
        and temporal.get("source_evidence") == policy["source_evidence"]
        and temporal.get("origin_rule") == "previous_day_23_59_59_utc"
        and temporal.get("test_used_for_selection") is False
        and temporal.get("final_test_split") == "test"
        and isinstance(folds, list)
        and [fold.get("split") for fold in folds if isinstance(fold, dict)] == expected_splits
        and len(folds) == len(expected_splits)
    )
    if valid:
        try:
            dates = [(str(fold["target_start"]), str(fold["target_end"])) for fold in folds]
            valid = all(
                first_start <= first_end < next_start <= next_end
                for (first_start, first_end), (next_start, next_end) in pairwise(dates)
            )
            valid = valid and all(int(fold["training_examples"]) > 0 for fold in folds)
            counts = dict.fromkeys(expected_splits, 0)
            keys: set[tuple[object, ...]] = set()
            for row in predictions:
                split = str(row["split"])
                if split not in counts:
                    valid = False
                    break
                counts[split] += 1
                key = (
                    split,
                    row["origin"],
                    row["forecast_date"],
                    row["product_id"],
                    row["store_id"],
                    row["channel"],
                )
                if key in keys:
                    valid = False
                    break
                keys.add(key)
            valid = valid and all(
                counts[fold["split"]] == int(fold["evaluated_rows"]) for fold in folds
            )
            for fold in folds:
                fold_rows = [row for row in predictions if row["split"] == fold["split"]]
                origin_day = date.fromisoformat(str(fold["target_start"])) - timedelta(days=1)
                expected_origin = f"{origin_day.isoformat()}T23:59:59+00:00"
                valid = valid and fold["origin"] == expected_origin
                valid = valid and all(
                    row["origin"] == fold["origin"]
                    and fold["target_start"] <= row["forecast_date"] <= fold["target_end"]
                    for row in fold_rows
                )
                valid = (
                    valid
                    and calculate_forecast_metrics(
                        fold_rows,
                        prediction_field="predicted_units",
                    )
                    == fold["model_metrics"]
                )
                valid = (
                    valid
                    and calculate_forecast_metrics(
                        fold_rows,
                        prediction_field="baseline_predicted_units",
                    )
                    == fold["baseline_metrics"]
                )
            final = [row for row in predictions if row["split"] == "test"]
            trained = calculate_forecast_metrics(final, prediction_field="predicted_units")
            baseline = calculate_forecast_metrics(
                final,
                prediction_field="baseline_predicted_units",
            )
            valid = valid and trained == report["trained_model_metrics"]
            valid = valid and baseline == report["baseline_metrics"]
        except (KeyError, TypeError, ValueError):
            valid = False
    return _check(
        "protocol",
        "passed" if valid else "failed",
        "fixed_origin_test" if valid else "invalid_or_inconsistent",
        expected_splits,
        len(predictions),
        "Chronological, disjoint folds and identical scored rows for RF and baseline."
        if valid
        else "Protocol, fold counts, keys, or final metrics are inconsistent.",
    )


def _coverage_check(temporal: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    folds = temporal.get("folds", [])
    valid = isinstance(folds, list) and len(folds) == policy["required_validation_windows"] + 1
    counts = []
    if valid:
        try:
            counts = [[int(fold["evaluated_rows"]), int(fold["eligible_rows"])] for fold in folds]
            required = Decimal(str(policy["required_coverage"]))
            valid = all(
                eligible > 0
                and 0 <= evaluated <= eligible
                and Decimal(evaluated) / Decimal(eligible) >= required
                for evaluated, eligible in counts
            )
        except (KeyError, TypeError, ValueError):
            valid = False
    return _check(
        "coverage",
        "passed" if valid else "failed",
        counts,
        policy["required_coverage"],
        sum(eligible for _, eligible in counts),
        "All eligible rows scored in every fold."
        if valid
        else "A fold has no eligible rows or has unscored eligible rows.",
    )


def _quality_check(report: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    trained = report.get("trained_model_metrics", {})
    baseline = report.get("baseline_metrics", {})
    trained = trained if isinstance(trained, dict) else {}
    baseline = baseline if isinstance(baseline, dict) else {}
    trained_wape = _number(trained.get("wape"))
    baseline_wape = _number(baseline.get("wape"))
    threshold = Decimal(str(policy["min_relative_wape_improvement_percent"]))
    row_count = trained.get("evaluated_rows")
    valid_metrics = (
        trained.get("status") == baseline.get("status") == "evaluable"
        and isinstance(row_count, int)
        and row_count == baseline.get("evaluated_rows")
        and row_count > 0
        and trained_wape is not None
        and trained_wape >= 0
        and baseline_wape is not None
        and baseline_wape > 0
    )
    improvement = (baseline_wape - trained_wape) / baseline_wape * 100 if valid_metrics else None
    status = (
        "passed"
        if improvement is not None and improvement >= threshold
        else "failed"
        if improvement is not None
        else "not_evaluable"
    )
    return _check(
        "final_quality",
        status,
        str(improvement) if improvement is not None else None,
        str(threshold),
        row_count if isinstance(row_count, int) else 0,
        "Final-test WAPE improvement meets the frozen relative threshold."
        if status == "passed"
        else "Final-test WAPE improvement is insufficient or undefined.",
    )


def _stability_check(temporal: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    folds = temporal.get("folds", [])
    folds = folds if isinstance(folds, list) else []
    validation = [
        fold
        for fold in folds
        if isinstance(fold, dict) and str(fold.get("split", "")).startswith("validation_")
    ]
    wins = 0
    evaluable = len(validation) == policy["required_validation_windows"]
    for fold in validation:
        model = fold.get("model_metrics", {})
        baseline = fold.get("baseline_metrics", {})
        model = model if isinstance(model, dict) else {}
        baseline = baseline if isinstance(baseline, dict) else {}
        model_wape = _number(model.get("wape"))
        baseline_wape = _number(baseline.get("wape"))
        if (
            model.get("status") != "evaluable"
            or baseline.get("status") != "evaluable"
            or model_wape is None
            or baseline_wape is None
        ):
            evaluable = False
            continue
        wins += model_wape < baseline_wape
    status = (
        "passed"
        if evaluable and wins >= policy["min_validation_wins"]
        else "failed"
        if evaluable
        else "not_evaluable"
    )
    return _check(
        "stability",
        status,
        wins,
        policy["min_validation_wins"],
        len(validation),
        "RF beats baseline in enough validation windows."
        if status == "passed"
        else "Validation evidence is missing or unstable.",
    )


def _segments_check(
    predictions: list[dict[str, object]],
    policy: dict[str, object],
) -> dict[str, object]:
    final = [row for row in predictions if row.get("split") == "test"]
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    try:
        for row in final:
            for field in policy["segment_fields"]:
                groups[(field, str(row[field]))].append(row)
        details = []
        threshold = Decimal(str(policy["max_segment_mae_regression_percent"]))
        for (field, value), rows in sorted(groups.items()):
            trained = calculate_forecast_metrics(rows, prediction_field="predicted_units")
            baseline = calculate_forecast_metrics(rows, prediction_field="baseline_predicted_units")
            trained_mae = _number(trained["mae"])
            baseline_mae = _number(baseline["mae"])
            passed = (
                len(rows) >= policy["min_segment_rows"]
                and trained_mae is not None
                and baseline_mae is not None
                and trained_mae <= baseline_mae * (1 + threshold / 100)
            )
            details.append(
                {
                    "field": field,
                    "value": value,
                    "rows": len(rows),
                    "trained_mae": trained["mae"],
                    "baseline_mae": baseline["mae"],
                    "passed": passed,
                }
            )
    except (KeyError, TypeError, ValueError):
        details = []
    valid = bool(details) and all(detail["passed"] for detail in details)
    return _check(
        "segments",
        "passed" if valid else "failed",
        details,
        {
            "min_rows": policy["min_segment_rows"],
            "max_mae_regression_percent": policy["max_segment_mae_regression_percent"],
        },
        len(final),
        "Every predefined store and channel segment meets sample and MAE limits."
        if valid
        else "A store or channel segment lacks rows or exceeds the MAE limit.",
    )


def evaluate_forecast_admission(
    report: dict[str, object],
    predictions: list[dict[str, object]],
    reproduction_evidence: dict[str, bool] | None = None,
) -> dict[str, object]:
    policy, policy_sha256 = load_policy()
    temporal = report.get("temporal_protocol")
    temporal = temporal if isinstance(temporal, dict) else {}
    evidence = reproduction_evidence or {}
    reproduced = all(evidence.get(name) is True for name in policy["reproduction_checks"])
    checks = [
        _protocol_check(report, predictions, policy),
        _coverage_check(temporal, policy),
        _quality_check(report, policy),
        _stability_check(temporal, policy),
        _segments_check(predictions, policy),
        _check(
            "reproduction",
            "passed" if reproduced else "not_ready",
            {name: evidence.get(name, False) for name in policy["reproduction_checks"]},
            policy["reproduction_checks"],
            len(predictions),
            "Source snapshot and saved model reproduce evaluated final-test predictions."
            if reproduced
            else "Source snapshot or model round-trip evidence is missing.",
        ),
    ]
    status = "candidate" if all(check["status"] == "passed" for check in checks) else "rejected"
    return {
        "policy_version": policy["policy_version"],
        "policy_sha256": policy_sha256,
        "use_case": policy["use_case"],
        "status": status,
        "checks": checks,
        "reason": "All required local checks passed."
        if status == "candidate"
        else "One or more required local checks did not pass.",
    }
