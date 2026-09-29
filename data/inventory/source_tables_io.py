"""CSV/Parquet parity for unpublished native inventory table candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

from data.generator.identity import canonical_json, file_sha256, json_sha256
from data.inventory.contract import UTC_TIMESTAMP_PATTERN, require, utc_timestamp
from data.inventory.source_tables import TableContext, normalize_tables, reconcile_tables
from data.inventory.source_tables_contract import (
    TABLE_CONTRACT_VERSION,
    TABLES,
    field_rules,
    table_contract_schema,
)

MONEY_FIELDS = {"unit_cost", "unit_price", "gross_revenue", "refund_amount"}
MAX_FILE_BYTES = 128 * 1024 * 1024
BATCH_ROWS = 8192


def table_schema(name: str) -> pa.Schema:
    fields = []
    for column, rule in field_rules(TABLES[name].model).items():
        if rule["type"] == "integer":
            arrow_type = pa.int64()
        elif rule["type"] == "boolean":
            arrow_type = pa.bool_()
        elif rule.get("pattern") == UTC_TIMESTAMP_PATTERN:
            arrow_type = pa.timestamp("us", tz="UTC")
        elif rule.get("pattern") == r"^\d{4}-\d{2}-\d{2}$":
            arrow_type = pa.date32()
        elif column in MONEY_FIELDS:
            arrow_type = pa.decimal128(38, 2)
        else:
            arrow_type = pa.string()
        fields.append(pa.field(column, arrow_type, nullable=rule["nullable"]))
    return pa.schema(
        fields,
        metadata={
            b"contract_version": TABLE_CONTRACT_VERSION.encode(),
            b"table": name.encode(),
            b"data_class": TABLES[name].data_class.encode(),
        },
    )


def _arrow_value(value: object, field: pa.Field) -> object:
    if value is None:
        return None
    if pa.types.is_timestamp(field.type):
        return utc_timestamp(str(value))
    if pa.types.is_date32(field.type):
        return date.fromisoformat(str(value))
    if pa.types.is_decimal(field.type):
        return Decimal(str(value))
    return value


def _native_value(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, ".2f")
    return value


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def _parse_csv(value: str, rule: dict) -> object:
    if value == "" and rule["nullable"]:
        return None
    if rule["type"] == "integer":
        parsed = int(value)
        require(str(parsed) == value, "Noncanonical inventory integer.")
        return parsed
    if rule["type"] == "boolean":
        require(value in {"true", "false"}, "Invalid inventory boolean.")
        return value == "true"
    return value


def _write_table(directory: Path, name: str, rows: list[dict]) -> dict:
    data_class = TABLES[name].data_class
    directory = directory / ("simulation_truth" if data_class == "simulation_truth" else "facts")
    directory.mkdir(exist_ok=True)
    csv_path, parquet_path = directory / (name + ".csv"), directory / (name + ".parquet")
    schema = table_schema(name)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=schema.names, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: _csv_value(v) for k, v in r.items()} for r in rows)
    with pq.ParquetWriter(parquet_path, schema, compression="zstd") as writer:
        for start in range(0, len(rows), BATCH_ROWS):
            batch = [
                {f.name: _arrow_value(r[f.name], f) for f in schema}
                for r in rows[start : start + BATCH_ROWS]
            ]
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    return {
        "rows": len(rows),
        "data_class": data_class,
        "grain": list(TABLES[name].grain),
        "csv_path": csv_path.relative_to(directory.parent).as_posix(),
        "parquet_path": parquet_path.relative_to(directory.parent).as_posix(),
        "csv_sha256": file_sha256(csv_path),
        "parquet_sha256": file_sha256(parquet_path),
        "logical_sha256": json_sha256(rows),
        "arrow_schema_sha256": hashlib.sha256(schema.serialize().to_pybytes()).hexdigest(),
    }


def _safe_file(directory: Path, relative: str) -> Path:
    path = directory / relative
    require(
        not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
        "Inventory table path escapes candidate directory.",
    )
    require(
        path.is_file() and path.stat().st_size <= MAX_FILE_BYTES,
        "Inventory table missing or exceeds file budget.",
    )
    return path


def read_tables(directory: Path) -> tuple[dict, dict, TableContext]:
    require(
        not directory.is_symlink() and not any(p.is_symlink() for p in directory.rglob("*")),
        "Symlink in inventory table candidate.",
    )
    receipt = json.loads(_safe_file(directory, "tables.json").read_text())
    require(
        set(receipt)
        == {
            "contract_version",
            "purpose",
            "candidate_id",
            "parent_execution_id",
            "context",
            "table_contract_sha256",
            "inventory_ready",
            "source_ready",
            "model_ready",
            "tables",
        },
        "Inventory candidate receipt fields disagree.",
    )
    require(
        receipt["contract_version"] == TABLE_CONTRACT_VERSION
        and receipt["purpose"] == "unpublished_inventory_table_candidate",
        "Unsupported inventory table candidate contract.",
    )
    require(
        all(receipt[k] is False for k in ("inventory_ready", "source_ready", "model_ready")),
        "Table candidate cannot claim source/model readiness.",
    )
    require(
        receipt["table_contract_sha256"] == json_sha256(table_contract_schema())
        and set(receipt["tables"]) == set(TABLES),
        "Inventory table allowlist or contract differs.",
    )
    context = TableContext.model_validate(receipt["context"])
    tables = {}
    for name, definition in TABLES.items():
        artifact = receipt["tables"][name]
        require(
            set(artifact)
            == {
                "rows",
                "data_class",
                "grain",
                "csv_path",
                "parquet_path",
                "csv_sha256",
                "parquet_sha256",
                "logical_sha256",
                "arrow_schema_sha256",
            },
            "Inventory artifact receipt fields disagree.",
        )
        class_dir = "simulation_truth" if definition.data_class == "simulation_truth" else "facts"
        require(
            artifact["data_class"] == definition.data_class
            and artifact["grain"] == list(definition.grain)
            and artifact["csv_path"] == f"{class_dir}/{name}.csv"
            and artifact["parquet_path"] == f"{class_dir}/{name}.parquet",
            "Inventory facts/truth placement or grain differs.",
        )
        csv_path, parquet_path = (
            _safe_file(directory, artifact[f + "_path"]) for f in ("csv", "parquet")
        )
        require(
            all(
                file_sha256(p) == artifact[f + "_sha256"]
                for p, f in ((csv_path, "csv"), (parquet_path, "parquet"))
            ),
            "Inventory table file checksum differs.",
        )
        schema = table_schema(name)
        with csv_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            require(
                reader.fieldnames == schema.names,
                "Inventory CSV header differs from native schema.",
            )
            rules = field_rules(definition.model)
            rows = []
            for r in reader:
                require(
                    set(r) == set(schema.names) and all(isinstance(v, str) for v in r.values()),
                    "Inventory CSV row width differs.",
                )
                rows.append(
                    definition.model.model_validate(
                        {k: _parse_csv(v, rules[k]) for k, v in r.items()}
                    ).model_dump()
                )
        parquet = pq.ParquetFile(parquet_path)
        require(
            parquet.schema_arrow.equals(schema, check_metadata=True)
            and artifact["arrow_schema_sha256"]
            == hashlib.sha256(schema.serialize().to_pybytes()).hexdigest(),
            "Inventory Parquet schema differs.",
        )
        native = [
            {k: _native_value(v) for k, v in r.items()}
            for b in parquet.iter_batches(batch_size=BATCH_ROWS)
            for r in b.to_pylist()
        ]
        require(
            rows == native
            and type(artifact["rows"]) is int
            and len(rows) == artifact["rows"]
            and json_sha256(rows) == artifact["logical_sha256"],
            "Inventory CSV/Parquet typed parity differs.",
        )
        tables[name] = rows
    require(
        normalize_tables(tables) == tables,
        "Inventory tables require canonical values and grain order.",
    )
    require(
        receipt["candidate_id"] == candidate_id(tables, context, receipt["parent_execution_id"]),
        "Inventory table candidate identity differs.",
    )
    expected_files = {
        "tables.json",
        *(a[k] for a in receipt["tables"].values() for k in ("csv_path", "parquet_path")),
    }
    require(
        {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        == expected_files,
        "Unallowlisted file in inventory table candidate.",
    )
    reconcile_tables(tables, context)
    return tables, receipt, context


def candidate_id(tables: dict, context: TableContext, parent_execution_id: str) -> str:
    require(
        re.fullmatch(r"source-inventory-candidate-sha256-[0-9a-f]{64}", parent_execution_id)
        is not None,
        "Invalid parent execution ID.",
    )
    return "inventory-tables-candidate-sha256-" + json_sha256(
        {
            "contract_version": TABLE_CONTRACT_VERSION,
            "table_contract_sha256": json_sha256(table_contract_schema()),
            "parent_execution_id": parent_execution_id,
            "context": context.model_dump(),
            "tables": {n: json_sha256(rows) for n, rows in tables.items()},
        }
    )


def write_tables(
    tables: dict, context: TableContext, output_root: Path, parent_execution_id: str
) -> Path:
    tables = normalize_tables(tables)
    reconcile_tables(tables, context)
    identifier = candidate_id(tables, context, parent_execution_id)
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / identifier
    if final.exists():
        read_tables(final)
        return final
    with TemporaryDirectory(prefix=".inventory-tables-", dir=output_root) as temporary:
        staging = Path(temporary) / "candidate"
        staging.mkdir()
        artifacts = {name: _write_table(staging, name, rows) for name, rows in tables.items()}
        receipt = {
            "contract_version": TABLE_CONTRACT_VERSION,
            "purpose": "unpublished_inventory_table_candidate",
            "candidate_id": identifier,
            "parent_execution_id": parent_execution_id,
            "context": context.model_dump(),
            "table_contract_sha256": json_sha256(table_contract_schema()),
            "inventory_ready": False,
            "source_ready": False,
            "model_ready": False,
            "tables": artifacts,
        }
        (staging / "tables.json").write_bytes(canonical_json(receipt) + b"\n")
        read_tables(staging)
        staging.rename(final)
    return final
