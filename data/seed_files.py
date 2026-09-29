"""Generate missing legacy seed CSVs after generated small stopped being tracked."""

from __future__ import annotations

import argparse
from pathlib import Path

from data.generator.configuration import DatasetGenerationConfig
from data.generator.csv_writer import CSV_WRITE_ORDER
from data.generator.main import generate_demo_dataset

ROOT = Path(__file__).resolve().parents[1]


def ensure_seed_files(profile: str, repository: Path = ROOT) -> Path:
    if profile not in {"demo", "small", "medium"}:
        msg = "Unsupported legacy seed profile."
        raise ValueError(msg)
    target = repository / "data" / ("demo" if profile == "demo" else "synthetic/" + profile)
    if target.is_symlink():
        msg = "Seed data directory must not be a symlink."
        raise ValueError(msg)
    files = [target / (name + ".csv") for name in CSV_WRITE_ORDER]
    if all(path.is_file() and not path.is_symlink() for path in files):
        return target
    if target.exists() and any(target.iterdir()):
        msg = "Incomplete seed directory; choose explicit generation instead of overwriting it."
        raise ValueError(msg)
    generate_demo_dataset(target, DatasetGenerationConfig(profile=profile))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare missing legacy seed files without replacing existing data."
    )
    parser.add_argument("--profile", choices=("demo", "small", "medium"), required=True)
    args = parser.parse_args()
    ensure_seed_files(args.profile)


if __name__ == "__main__":
    main()
