"""Two fresh producer processes: verified source 2.8 → sealed event-day declarations."""
# ruff: noqa: INP001 - standalone acceptance script, no package import

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.anomalies.example import example_plan  # noqa: E402
from data.anomalies.physical_scenarios import physical_example_plan  # noqa: E402
from data.anomalies.source_process import build_tables  # noqa: E402
from data.day_coverage.package import build, verify  # noqa: E402
from data.generator.configuration import DatasetGenerationConfig  # noqa: E402
from data.generator.identity import file_sha256  # noqa: E402
from data.inventory.contract import require  # noqa: E402
from data.inventory.run_source_dataset import default_inventory_config  # noqa: E402
from data.inventory.source_dataset_io import write_source_dataset  # noqa: E402


def worker(workspace: Path) -> dict:
    started = time.monotonic()
    cases = []
    for name, factory in (("demand", example_plan), ("physical", physical_example_plan)):
        generation = DatasetGenerationConfig(
            profile="ai-smoke", days=30, products=8, stores=3, warehouses=2
        )
        config = default_inventory_config(generation)
        plan = factory(generation)
        tables, context = build_tables(generation, plan, config)
        source = write_source_dataset(
            tables, context, generation, config, workspace / name / "source", scenario_plan=plan
        )
        before = {
            p.relative_to(source).as_posix(): file_sha256(p)
            for p in source.rglob("*")
            if p.is_file()
        }
        result = build(source, workspace / name / "coverage")
        directory = Path(result["directory"])
        manifest = verify(directory, source)
        require(
            before
            == {
                p.relative_to(source).as_posix(): file_sha256(p)
                for p in source.rglob("*")
                if p.is_file()
            },
            "coverage_modified_source",
        )
        cases.append(
            {
                "case": name,
                "source_dataset_id": source.name,
                "coverage_id": manifest.coverage_id,
                "rows_sha256": manifest.descriptor.rows_sha256,
                "row_count": manifest.descriptor.row_count,
                "files": {p.name: file_sha256(p) for p in directory.iterdir()},
            }
        )
    elapsed = time.monotonic() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    require(elapsed <= 300 and rss <= 1024, "coverage_process_budget_exceeded")
    return {"elapsed_seconds": round(elapsed, 3), "peak_rss_mib": round(rss, 3), "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        result = worker(args.worker.resolve())
    else:
        runs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="ai07-day-coverage-") as tmp:
                run = subprocess.run(  # noqa: S603 - fixed interpreter/script
                    [sys.executable, "-I", str(Path(__file__).resolve()), "--worker", tmp],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=360,
                )
                if run.returncode:
                    message = "day coverage worker failed: " + run.stderr[-8192:]
                    raise RuntimeError(message)
                runs.append(json.loads(run.stdout))
        require(runs[0]["cases"] == runs[1]["cases"], "coverage_not_reproducible")
        result = {
            "status": "passed",
            "limits": {"seconds_per_process": 300, "peak_rss_mib": 1024},
            "runs": runs,
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
