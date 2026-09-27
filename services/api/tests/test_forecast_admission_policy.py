from __future__ import annotations

from datetime import date, timedelta

import pytest

from ml.evaluation.metrics import calculate_forecast_metrics
from ml.policy.forecast_admission import evaluate_forecast_admission, load_policy


def _eligible_report() -> tuple[dict[str, object], list[dict[str, object]]]:
    predictions: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    for index, split in enumerate(("validation_1", "validation_2", "validation_3", "test")):
        start = date(2026, 1, 1) + timedelta(days=index * 7)
        end = start + timedelta(days=6)
        origin = (start - timedelta(days=1)).isoformat() + "T23:59:59+00:00"
        rows = [
            {
                "split": split,
                "origin": origin,
                "forecast_date": start.isoformat(),
                "product_id": f"p{number}",
                "store_id": "store-1",
                "channel": "web",
                "actual_units": 100,
                "predicted_units": 104,
                "baseline_predicted_units": 110,
            }
            for number in range(20)
        ]
        predictions.extend(rows)
        folds.append({
            "split": split,
            "origin": origin,
            "target_start": start.isoformat(),
            "target_end": end.isoformat(),
            "training_examples": 20,
            "eligible_rows": 20,
            "evaluated_rows": 20,
            "model_metrics": calculate_forecast_metrics(rows, prediction_field="predicted_units"),
            "baseline_metrics": calculate_forecast_metrics(
                rows, prediction_field="baseline_predicted_units",
            ),
        })
    report = {
        "evaluation_scope": "synthetic_fixed_origin_horizon_v1",
        "temporal_protocol": {
            "protocol_version": "synthetic_fixed_origin_v1",
            "source_evidence": "synthetic_profile_completeness_assumption_v1",
            "origin_rule": "previous_day_23_59_59_utc",
            "test_used_for_selection": False,
            "final_test_split": "test",
            "folds": folds,
        },
        "trained_model_metrics": folds[-1]["model_metrics"],
        "baseline_metrics": folds[-1]["baseline_metrics"],
    }
    return report, predictions


def _check_status(decision: dict[str, object], check_id: str) -> str:
    return next(check["status"] for check in decision["checks"] if check["check_id"] == check_id)


def test_frozen_local_policy_can_admit_complete_evidence() -> None:
    report, predictions = _eligible_report()
    decision = evaluate_forecast_admission(
        report, predictions, {"source_snapshot": True, "artifact_roundtrip": True},
    )
    policy, checksum = load_policy()
    assert decision["policy_version"] == policy["policy_version"]
    assert decision["policy_sha256"] == checksum
    assert decision["status"] == "candidate"
    assert {check["status"] for check in decision["checks"]} == {"passed"}


@pytest.mark.parametrize("evidence", [
    None,
    {"source_snapshot": False, "artifact_roundtrip": True},
    {"source_snapshot": True, "artifact_roundtrip": False},
])
def test_missing_reproduction_evidence_blocks_candidate(evidence) -> None:
    report, predictions = _eligible_report()
    decision = evaluate_forecast_admission(report, predictions, evidence)
    assert decision["status"] == "rejected"
    assert _check_status(decision, "reproduction") == "not_ready"


@pytest.mark.parametrize("change,check_id", [
    ("test_selected", "protocol"),
    ("missing_rows", "coverage"),
    ("insufficient_quality", "final_quality"),
    ("unstable", "stability"),
    ("small_segment", "segments"),
])
def test_each_failed_gate_blocks_candidate(change: str, check_id: str) -> None:
    report, predictions = _eligible_report()
    folds = report["temporal_protocol"]["folds"]
    if change == "test_selected":
        report["temporal_protocol"]["test_used_for_selection"] = True
    elif change == "missing_rows":
        folds[0]["eligible_rows"] = 21
    elif change == "insufficient_quality":
        for row in predictions:
            if row["split"] == "test":
                row["predicted_units"] = 110
        folds[-1]["model_metrics"] = calculate_forecast_metrics(
            predictions[-20:], prediction_field="predicted_units",
        )
        report["trained_model_metrics"] = folds[-1]["model_metrics"]
    elif change == "unstable":
        for row in predictions:
            if row["split"] in {"validation_1", "validation_2"}:
                row["predicted_units"] = 110
        for fold in folds[:2]:
            rows = [row for row in predictions if row["split"] == fold["split"]]
            fold["model_metrics"] = calculate_forecast_metrics(
                rows, prediction_field="predicted_units",
            )
    elif change == "small_segment":
        for row in predictions[-5:]:
            row["store_id"] = "store-2"
    decision = evaluate_forecast_admission(
        report, predictions, {"source_snapshot": True, "artifact_roundtrip": True},
    )
    assert decision["status"] == "rejected"
    assert _check_status(decision, check_id) != "passed"


def test_tampered_fold_metric_does_not_pass_protocol() -> None:
    report, predictions = _eligible_report()
    report["temporal_protocol"]["folds"][0]["model_metrics"]["wape"] = "0.0000"
    decision = evaluate_forecast_admission(
        report, predictions, {"source_snapshot": True, "artifact_roundtrip": True},
    )
    assert decision["status"] == "rejected"
    assert _check_status(decision, "protocol") == "failed"


def test_missing_or_undefined_final_metric_cannot_admit_model() -> None:
    report, predictions = _eligible_report()
    report["trained_model_metrics"]["wape"] = None
    decision = evaluate_forecast_admission(
        report, predictions, {"source_snapshot": True, "artifact_roundtrip": True},
    )
    assert decision["status"] == "rejected"
    assert _check_status(decision, "final_quality") == "not_evaluable"

    empty = evaluate_forecast_admission(
        report, [], {"source_snapshot": True, "artifact_roundtrip": True},
    )
    assert empty["status"] == "rejected"
    assert _check_status(empty, "protocol") == "failed"
