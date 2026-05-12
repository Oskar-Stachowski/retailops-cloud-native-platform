from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DIR = REPO_ROOT / "ml" / "contracts"
FEATURE_SCHEMA_PATH = CONTRACT_DIR / "demand_forecast_features.schema.json"
MANIFEST_SCHEMA_PATH = CONTRACT_DIR / "demand_forecast_feature_manifest.schema.json"
FEATURE_EXAMPLE_PATH = CONTRACT_DIR / "demand_forecast_features.example.jsonl"
MANIFEST_EXAMPLE_PATH = CONTRACT_DIR / "demand_forecast_feature_manifest.example.json"

EXPECTED_GRAIN = ["date", "product_id", "store_id", "channel"]
EXPECTED_TARGET = "units_sold"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def required_fields(schema: dict[str, Any]) -> set[str]:
    return set(schema["required"])


def test_feature_contract_defines_forecasting_grain_and_target() -> None:
    schema = load_json(FEATURE_SCHEMA_PATH)
    properties = schema["properties"]

    assert schema["additionalProperties"] is False
    assert required_fields(schema).issuperset({*EXPECTED_GRAIN, EXPECTED_TARGET})
    assert properties[EXPECTED_TARGET]["description"].startswith("Forecast target")

    for grain_field in EXPECTED_GRAIN:
        assert grain_field in properties


def test_manifest_contract_references_feature_schema_grain_and_target() -> None:
    schema = load_json(MANIFEST_SCHEMA_PATH)
    properties = schema["properties"]

    assert properties["dataset_name"]["const"] == "retailops-demand-forecast-features"
    assert properties["feature_schema"]["const"] == "demand_forecast_features.schema.json"
    assert [item["const"] for item in properties["grain"]["prefixItems"]] == EXPECTED_GRAIN
    assert properties["target"]["const"] == EXPECTED_TARGET


def test_feature_example_matches_declared_contract_fields() -> None:
    schema = load_json(FEATURE_SCHEMA_PATH)
    allowed_fields = set(schema["properties"])
    required = required_fields(schema)
    example_rows = [
        json.loads(line)
        for line in FEATURE_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert example_rows
    for row in example_rows:
        assert required.issubset(row)
        assert set(row).issubset(allowed_fields)
        assert row["schema_version"] == schema["properties"]["schema_version"]["const"]
        assert row[EXPECTED_TARGET] >= 0


def test_manifest_example_matches_declared_contract_fields() -> None:
    schema = load_json(MANIFEST_SCHEMA_PATH)
    manifest = load_json(MANIFEST_EXAMPLE_PATH)

    assert set(schema["required"]).issubset(manifest)
    assert set(manifest).issubset(schema["properties"])
    assert manifest["feature_schema"] == schema["properties"]["feature_schema"]["const"]
    assert manifest["grain"] == EXPECTED_GRAIN
    assert manifest["target"] == EXPECTED_TARGET
