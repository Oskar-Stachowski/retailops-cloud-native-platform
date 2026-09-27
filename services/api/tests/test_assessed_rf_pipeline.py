from __future__ import annotations

import csv
import json

import pytest

from ml.experiments.assessed_run import load_assessed_run
from ml.experiments.identity import RUN_MANIFEST_FILENAME, file_sha256
from ml.inference.batch_forecast import (
    BATCH_MANIFEST_FILENAME,
    BATCH_PREDICTIONS_FILENAME,
    BatchInferenceConfig,
    load_verified_batch_manifest,
    run_batch_inference,
)
from ml.metadata.model_registry import MODEL_METADATA_FILENAME
from ml.metadata.verified_rf import persist_verified_rf_metadata
from ml.models.random_forest_forecast import (
    METRICS_FILENAME,
    MODEL_ARTIFACT_FILENAME,
    PREDICTIONS_FILENAME,
)
from ml.observability.model_performance_metrics import (
    MODEL_PERFORMANCE_SNAPSHOT_FILENAME,
    ModelPerformanceMetricsConfig,
    generate_model_performance_metrics,
)


def test_assessed_run_verifies_and_reloads_same_model(assessed_rf_run_dir) -> None:
    run = load_assessed_run(assessed_rf_run_dir)
    assert run.metrics["model_id"] == "sha256:" + file_sha256(
        assessed_rf_run_dir / MODEL_ARTIFACT_FILENAME,
    )
    assert run.metrics["experiment_id"] == run.manifest["experiment_id"]
    assert run.metadata["run_id"] == run.metrics["run_id"]
    assert run.predictions
    assert run.panel


def test_batch_metadata_and_metrics_share_assessed_identity(
    assessed_rf_run_dir, tmp_path, monkeypatch,
) -> None:
    def no_retraining(*_args, **_kwargs):
        msg = "Unexpected retraining or baseline fallback"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "ml.models.random_forest_forecast.train_random_forest_forecast_model", no_retraining,
    )
    monkeypatch.setattr(
        "ml.models.baseline_forecast.train_baseline_forecast_model", no_retraining,
    )
    metadata_dir = tmp_path / "metadata"
    inference_dir = tmp_path / "inference"
    metrics_dir = tmp_path / "metrics"
    run = load_assessed_run(assessed_rf_run_dir)
    metadata = persist_verified_rf_metadata(run, metadata_dir)
    manifest = run_batch_inference(BatchInferenceConfig(
        experiment_dir=assessed_rf_run_dir,
        output_dir=inference_dir,
        metadata_output_dir=metadata_dir,
    ))
    first_batch_rows = list(csv.DictReader((inference_dir / BATCH_PREDICTIONS_FILENAME).open()))
    snapshot = generate_model_performance_metrics(ModelPerformanceMetricsConfig(
        experiment_dir=assessed_rf_run_dir,
        output_dir=metrics_dir,
        metadata_output_dir=metadata_dir,
        inference_output_dir=inference_dir,
    ))
    batch_rows = list(csv.DictReader((inference_dir / BATCH_PREDICTIONS_FILENAME).open()))
    written_manifest = json.loads((inference_dir / BATCH_MANIFEST_FILENAME).read_text())
    written_metadata = json.loads((metadata_dir / MODEL_METADATA_FILENAME).read_text())
    written_snapshot = json.loads((metrics_dir / MODEL_PERFORMANCE_SNAPSHOT_FILENAME).read_text())
    assert batch_rows
    assert {row["model_id"] for row in batch_rows} == {run.metrics["model_id"]}
    assert {row["experiment_id"] for row in batch_rows} == {run.metrics["experiment_id"]}
    assert {row["run_id"] for row in batch_rows} == {run.metrics["run_id"]}
    assert {row["feature_dataset_id"] for row in batch_rows} == {
        run.metrics["feature_dataset_id"],
    }
    assert {row["horizon_day"] for row in batch_rows} == {str(day) for day in range(1, 8)}
    assert manifest["model_id"] == written_manifest["model_id"]
    assert [
        (row["product_id"], row["store_id"], row["forecast_date"], row["predicted_units"])
        for row in first_batch_rows
    ] == [
        (row["product_id"], row["store_id"], row["forecast_date"], row["predicted_units"])
        for row in batch_rows
    ]
    assert metadata["model_id"] == manifest["model_id"] == snapshot["model_id"]
    assert written_metadata["experiment_id"] == snapshot["experiment_id"]
    assert written_metadata["run_id"] == snapshot["run_id"]
    assert snapshot == written_snapshot
    assert snapshot["evaluation"]["wape"] == run.metrics["trained_model_metrics"]["wape"]
    assert manifest["source_run_manifest_sha256"] == run.manifest_sha256
    assert (assessed_rf_run_dir / RUN_MANIFEST_FILENAME).exists()


def test_tampered_model_artifact_is_rejected_before_inference(assessed_rf_run_dir, tmp_path) -> None:
    with (assessed_rf_run_dir / MODEL_ARTIFACT_FILENAME).open("ab") as file:
        file.write(b"changed")
    output_dir = tmp_path / "inference"
    with pytest.raises(ValueError, match="checksum mismatch"):
        run_batch_inference(BatchInferenceConfig(
            experiment_dir=assessed_rf_run_dir, output_dir=output_dir,
            metadata_output_dir=tmp_path / "metadata",
        ))
    assert not output_dir.exists()


def test_tampered_prediction_identity_is_rejected(assessed_rf_run_dir) -> None:
    prediction_path = assessed_rf_run_dir / PREDICTIONS_FILENAME
    content = prediction_path.read_text(encoding="utf-8")
    prediction_path.write_text(content.replace("random-forest-v3", "random-forest-v4", 1),
                               encoding="utf-8")
    manifest_path = assessed_rf_run_dir / RUN_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"][PREDICTIONS_FILENAME] = file_sha256(prediction_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="prediction content mismatch"):
        load_assessed_run(assessed_rf_run_dir)


def test_tampered_batch_predictions_cannot_feed_performance_snapshot(
    assessed_rf_run_dir, tmp_path,
) -> None:
    output_dir = tmp_path / "inference"
    run_batch_inference(BatchInferenceConfig(
        experiment_dir=assessed_rf_run_dir,
        output_dir=output_dir,
        metadata_output_dir=tmp_path / "metadata",
    ))
    path = output_dir / BATCH_PREDICTIONS_FILENAME
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    rows[0]["predicted_units"] = str(int(rows[0]["predicted_units"]) + 1)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Batch artifacts"):
        load_verified_batch_manifest(output_dir, load_assessed_run(assessed_rf_run_dir))


def test_rehashed_wrong_model_identity_is_rejected(assessed_rf_run_dir) -> None:
    metrics_path = assessed_rf_run_dir / METRICS_FILENAME
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["model_id"] = "sha256:wrong-model"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    manifest_path = assessed_rf_run_dir / RUN_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"][METRICS_FILENAME] = file_sha256(metrics_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="model identity mismatch"):
        load_assessed_run(assessed_rf_run_dir)


def test_rehashed_status_override_cannot_promote_model(assessed_rf_run_dir) -> None:
    metrics_path = assessed_rf_run_dir / METRICS_FILENAME
    metadata_path = assessed_rf_run_dir / MODEL_METADATA_FILENAME
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metrics["model_status"] = "approved"
    metadata["status"] = "approved"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    manifest_path = assessed_rf_run_dir / RUN_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"][METRICS_FILENAME] = file_sha256(metrics_path)
    manifest["artifact_sha256"][MODEL_METADATA_FILENAME] = file_sha256(metadata_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="model status mismatch"):
        load_assessed_run(assessed_rf_run_dir)
