"""Default AI source 2.7 publication; legacy 2.6 remains an explicit compatibility path."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from data.export.inventory_snapshot import export_inventory_snapshot
from data.export.policy import GENERATED_ROOT, generated_target
from data.inventory.qualification_io import write_qualification
from data.inventory.run_source_dataset import run


def generate_snapshot(
    config: DatasetGenerationConfig,
    output_root: Path,
    *,
    include_truth: bool = False,
    chunk_rows: int = 8192,
    required_use_cases: tuple[str, ...] = ("forecast_source", "inventory_source"),
) -> dict:
    output_root = generated_target(output_root)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="inventory-source-", dir=GENERATED_ROOT) as temporary:
        root = Path(temporary)
        source = run(config, root / "sources")
        directory = Path(source["directory"])
        qualification = write_qualification(directory, root / "qualifications")
        return export_inventory_snapshot(
            directory,
            source["dataset_id"],
            qualification,
            output_root,
            include_truth=include_truth,
            chunk_rows=chunk_rows,
            required_use_cases=required_use_cases,
        )


if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig
