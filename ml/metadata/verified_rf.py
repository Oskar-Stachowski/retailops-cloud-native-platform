"""Persist metadata only from a verified, already evaluated RF run."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ml.experiments.assessed_run import AssessedRun, load_assessed_run
from ml.metadata.model_registry import (
    MODEL_METADATA_FILENAME,
    MODEL_REGISTRY_FILENAME,
    default_metadata_output_dir,
)


def persist_verified_rf_metadata(run: AssessedRun, output_dir: Path) -> dict[str, object]:
    if output_dir.resolve().is_relative_to(run.directory):
        msg = "Metadata output must not overwrite the assessed experiment."
        raise ValueError(msg)
    metadata = {
        **run.metadata,
        "source_run_manifest_sha256": run.manifest_sha256,
        "assessed_experiment_dir": str(run.directory),
        "verified_at": datetime.now(UTC).isoformat(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / MODEL_METADATA_FILENAME
    registry_path = output_dir / MODEL_REGISTRY_FILENAME
    records: dict[str, dict[str, object]] = {}
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                records[str(record["model_id"])] = record
    records[str(metadata["model_id"])] = metadata
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    registry_path.write_text(
        "".join(json.dumps(records[key], sort_keys=True) + "\n" for key in sorted(records)),
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register one verified RF experiment locally.")
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run = load_assessed_run(args.experiment_dir)
    output_dir = args.output_dir or default_metadata_output_dir(str(run.metrics["profile"]))
    metadata = persist_verified_rf_metadata(run, output_dir)
    print(  # noqa: T201 - CLI output
        f"Verified RF metadata persisted: {metadata['model_id']} ({metadata['status']})",
    )
    print(f"Output directory: {output_dir}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
