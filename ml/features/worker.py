from __future__ import annotations

import argparse
import json
import sys

from ml.features.ai_demand import ai_feature_rows, validate_ai_records
from ml.features.fact_input import validate_fact_input


def transform(payload: dict) -> list[dict]:
    tables = validate_fact_input(payload)
    rows = ai_feature_rows(
        tables["daily_demand_observations"],
        tables["product_catalog"],
        tables["catalog_categories"],
        tables.get("daily_demand_versions"),
    )
    validate_ai_records(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Facts-only feature/runtime worker.")
    parser.parse_args()
    try:
        rows = transform(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError, ArithmeticError):
        parser.exit(1, "Feature input rejected.\n")
    json.dump(rows, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
