"""Load one evaluated RF run and verify its immutable local evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import joblib

from ml.experiments.identity import (
    INPUT_MANIFEST_FILENAME,
    RUN_MANIFEST_FILENAME,
    SOURCE_ARCHIVE_FILENAME,
    canonical_sha256,
    file_sha256,
    logical_rows_sha256,
)
from ml.features.demand_forecast import SCHEMA_VERSION as FEATURE_SCHEMA_VERSION
from ml.models.random_forest_forecast import (
    EVALUATION_SCOPE,
    METRICS_FILENAME,
    MODEL_ARTIFACT_FILENAME,
    MODEL_METADATA_FILENAME,
    MODEL_NAME,
    MODEL_VERSION,
    PANEL_FILENAME,
    PREDICTIONS_FILENAME,
    _artifact_roundtrip_matches,
)
from ml.policy.forecast_admission import evaluate_forecast_admission

if TYPE_CHECKING:
    from sklearn.pipeline import Pipeline

PREDICTION_INTEGER_FIELDS = (
    "horizon_day",
    "predicted_units",
    "baseline_predicted_units",
    "actual_units",
)
PANEL_INTEGER_FIELDS = ("day_of_week", "week_of_year", "month")
PANEL_BOOLEAN_FIELDS = (
    "is_weekend",
    "is_active_assortment",
    "location_open",
    "source_data_complete",
)
REQUIRED_ARTIFACTS = (
    MODEL_ARTIFACT_FILENAME,
    METRICS_FILENAME,
    MODEL_METADATA_FILENAME,
    PREDICTIONS_FILENAME,
    PANEL_FILENAME,
    INPUT_MANIFEST_FILENAME,
    SOURCE_ARCHIVE_FILENAME,
)


@dataclass(frozen=True)
class AssessedRun:
    directory: Path
    manifest: dict[str, object]
    inputs: dict[str, object]
    metrics: dict[str, object]
    metadata: dict[str, object]
    predictions: list[dict[str, object]]
    panel: list[dict[str, object]]
    model: Pipeline

    @property
    def manifest_sha256(self) -> str:
        return file_sha256(self.directory / RUN_MANIFEST_FILENAME)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        msg = f"Expected a JSON object: {path.name}"
        raise TypeError(msg)
    return value


def _parse_boolean(value: str) -> bool | None:
    if value == "":
        return None
    if value not in {"True", "False"}:
        msg = "Invalid boolean in saved daily panel."
        raise ValueError(msg)
    return value == "True"


def _read_predictions(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for field in PREDICTION_INTEGER_FIELDS:
            row[field] = int(row[field])
    return rows


def _read_panel(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for field in PANEL_INTEGER_FIELDS:
            row[field] = int(row[field])
        for field in PANEL_BOOLEAN_FIELDS:
            row[field] = _parse_boolean(row[field])
        row["units_sold"] = int(row["units_sold"]) if row["units_sold"] else None
    return rows


def _source_archive_matches(archive_path: Path, checksums: dict[str, str]) -> bool:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            return bool(checksums) and all(
                hashlib.sha256(archive.read(name)).hexdigest() == checksum
                for name, checksum in checksums.items()
            )
    except (KeyError, OSError, zipfile.BadZipFile):
        return False


def _require(condition: bool, reason: str) -> None:  # noqa: FBT001 - verification helper
    if not condition:
        msg = f"Assessed RF run failed verification: {reason}."
        raise ValueError(msg)


def load_assessed_run(directory: Path) -> AssessedRun:
    """Refuse missing, mismatched, or unscored artifacts before any inference."""
    directory = directory.resolve()
    manifest = _read_json(directory / RUN_MANIFEST_FILENAME)
    checksums = manifest.get("artifact_sha256")
    _require(isinstance(checksums, dict), "missing artifact checksums")
    _require(set(REQUIRED_ARTIFACTS) <= set(checksums), "required artifact omitted")
    for name, checksum in checksums.items():
        _require(Path(name).name == name, "invalid artifact name")
        _require(file_sha256(directory / name) == checksum, f"checksum mismatch for {name}")

    inputs = _read_json(directory / INPUT_MANIFEST_FILENAME)
    metrics = _read_json(directory / METRICS_FILENAME)
    metadata = _read_json(directory / MODEL_METADATA_FILENAME)
    predictions = _read_predictions(directory / PREDICTIONS_FILENAME)
    panel = _read_panel(directory / PANEL_FILENAME)
    model_id = "sha256:" + file_sha256(directory / MODEL_ARTIFACT_FILENAME)
    experiment_id = "rf-" + canonical_sha256(inputs)[:20]
    for record in (manifest, metrics, metadata):
        _require(record.get("experiment_id") == experiment_id, "experiment identity mismatch")
        _require(record.get("model_id") == model_id, "model identity mismatch")
        _require(record.get("run_id") == metrics.get("run_id"), "run identity mismatch")
    _require(
        manifest.get("evaluation_scope") == metrics.get("evaluation_scope") == EVALUATION_SCOPE,
        "evaluation scope mismatch",
    )
    _require(
        metrics.get("model_name") == metadata.get("model_name") == MODEL_NAME
        and metrics.get("model_version") == metadata.get("model_version") == MODEL_VERSION,
        "model name or version mismatch",
    )
    features = inputs.get("features")
    source = inputs.get("source")
    _require(isinstance(features, dict) and isinstance(source, dict), "input identity missing")
    _require(features.get("schema_version") == FEATURE_SCHEMA_VERSION, "feature schema mismatch")
    _require(
        features.get("dataset_id")
        == metrics.get("feature_dataset_id")
        == metadata.get("feature_dataset_id"),
        "feature dataset mismatch",
    )
    _require(
        logical_rows_sha256(predictions) == manifest.get("predictions_logical_sha256"),
        "prediction content mismatch",
    )
    _require(
        logical_rows_sha256(panel)
        == manifest.get("panel_logical_sha256")
        == features.get("panel_logical_sha256"),
        "panel content mismatch",
    )
    source_hashes = source.get("source_files_sha256")
    _require(isinstance(source_hashes, dict), "source identity missing")
    source_snapshot = _source_archive_matches(
        directory / SOURCE_ARCHIVE_FILENAME,
        source_hashes,
    )
    _require(source_snapshot, "source snapshot mismatch")
    model = joblib.load(directory / MODEL_ARTIFACT_FILENAME)
    roundtrip = _artifact_roundtrip_matches(
        model,
        directory / MODEL_ARTIFACT_FILENAME,
        panel,
        predictions,
        metrics,
    )
    _require(roundtrip, "saved model does not reproduce evaluated predictions")
    decision = evaluate_forecast_admission(
        metrics,
        predictions,
        {"source_snapshot": source_snapshot, "artifact_roundtrip": roundtrip},
    )
    _require(
        decision == metrics.get("admission_decision") == metadata.get("admission_decision"),
        "admission decision mismatch",
    )
    _require(
        metrics.get("model_status") == metadata.get("status") == decision["status"],
        "model status mismatch",
    )
    return AssessedRun(
        directory,
        manifest,
        inputs,
        metrics,
        metadata,
        predictions,
        panel,
        model,
    )
