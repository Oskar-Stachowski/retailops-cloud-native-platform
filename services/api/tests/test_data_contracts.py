from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.seed_demo_data import TABLE_CONFIGS

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
DATA_DIR = REPO_ROOT / "data" / "demo"
DATA_CONTRACT_PATH = REPO_ROOT / "data" / "contracts" / "retailops_seed_dataset.contract.json"
EVENT_CONTRACT_PATH = (
    REPO_ROOT / "events" / "contracts" / "retailops-realtime-events.v1.contract.json"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or [])


def test_seed_dataset_contract_exists_and_has_seed_tables() -> None:
    contract = read_json(DATA_CONTRACT_PATH)

    assert contract["contract_name"] == "retailops_seed_dataset"
    assert contract["dataset"]["default_path"] == "data/demo"
    assert contract["validation"]["required_quality_status"] == "passed"

    contract_tables = {table["name"] for table in contract["tables"]}
    assert set(contract["validation"]["seeded_db_tables"]).issubset(contract_tables)


def test_contract_required_columns_match_demo_csv_headers() -> None:
    contract = read_json(DATA_CONTRACT_PATH)

    for table in contract["tables"]:
        csv_path = DATA_DIR / table["filename"]
        actual_header = set(read_csv_header(csv_path))
        required_columns = set(table["required_columns"])

        assert required_columns.issubset(actual_header), table["name"]


def test_seed_script_table_configs_are_covered_by_data_contract() -> None:
    contract = read_json(DATA_CONTRACT_PATH)
    contract_columns = {
        table["name"]: set(table["required_columns"])
        for table in contract["tables"]
    }

    for table_config in TABLE_CONFIGS:
        assert table_config.name in contract_columns
        assert set(table_config.columns).issubset(contract_columns[table_config.name])


def test_event_contract_documents_required_event_envelope() -> None:
    contract = read_json(EVENT_CONTRACT_PATH)

    required_envelope_fields = set(contract["envelope"]["required_fields"])
    assert {
        "event_id",
        "event_type",
        "topic",
        "schema_version",
        "source",
        "correlation_id",
        "occurred_at",
        "ingested_at",
        "payload",
    }.issubset(required_envelope_fields)
    assert "sale_completed" in contract["supported_event_types"]
    assert "realtime_event_log" == contract["persistence"]["event_log_table"]
