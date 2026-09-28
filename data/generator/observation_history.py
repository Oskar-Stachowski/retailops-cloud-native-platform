"""Versioned daily observed quantities; simulator truth is never a history input."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING

from data.generator.business_calendar import utc_midnight
from data.generator.common import deterministic_uuid
from data.generator.demand_grid import demand_grid
from data.generator.demand_schema import DEMAND_GRAIN
from data.generator.dimension_contract import field_rule
from ml.features.observation_history import (
    HISTORY_VERSION,
    aggregate_versions,
    append_version,
    utc,
    validate_history,
)

HISTORY_TABLE = "daily_demand_versions"
if TYPE_CHECKING:
    from data.generator.configuration import ResolvedGenerationConfig
HISTORY_COLUMNS = [
    "id",
    "observation_id",
    *DEMAND_GRAIN,
    "version",
    "observed_units",
    "observation_status",
    "available_at",
    "history_policy_version",
]


def uses_history(profile: str, schema_version: str = "2.6.0") -> bool:
    return profile.startswith("ai-") and schema_version == "2.6.0"


def build_daily_versions(tables: dict, config: ResolvedGenerationConfig) -> list[dict]:
    grid, _ = demand_grid(tables, config)
    references = {row["sale_id"]: row for row in tables["sale_price_references"]}
    grouped = defaultdict(list)
    for sale in tables["sales"]:
        ref = references[sale["id"]]
        key = tuple(ref[field] for field in DEMAND_GRAIN)
        grouped[key].append(
            (
                sale["id"],
                max(utc(sale.get("ingested_at") or sale["sold_at"]), utc(ref["as_of_time"])),
                int(sale["quantity"]),
            )
        )
    result = []
    for key, flags in sorted(grid.items()):
        close = utc(utc_midnight(date.fromisoformat(key[0]) + timedelta(days=1)))
        history = aggregate_versions(grouped[key], close)
        if flags["location_open"] == "false":
            history[0]["observation_status"] = "closed"
        observation_id = deterministic_uuid("daily_demand", ":".join(key))
        result.extend(_source_row(key, observation_id, version) for version in history)
    return result


def _source_row(key: tuple, observation_id: str, version: dict) -> dict:
    return {
        "id": deterministic_uuid(
            "daily_demand_version", observation_id + ":" + str(version["version"])
        ),
        "observation_id": observation_id,
        **dict(zip(DEMAND_GRAIN, key, strict=True)),
        "version": str(version["version"]),
        "observed_units": "" if version["units_sold"] is None else str(version["units_sold"]),
        "observation_status": version["observation_status"],
        "available_at": version["available_at"],
        "history_policy_version": HISTORY_VERSION,
    }


def feature_history(rows: list[dict]) -> list[dict]:
    return validate_history(
        [
            {
                "version": int(row["version"]),
                "available_at": row["available_at"],
                "units_sold": None if row["observed_units"] == "" else int(row["observed_units"]),
                "observation_status": row["observation_status"],
            }
            for row in sorted(rows, key=lambda row: int(row["version"]))
        ]
    )


def append_daily_revision(
    rows: list[dict],
    observation_id: str,
    units: int | None,
    available_at: str,
    status: str | None = None,
) -> list[dict]:
    previous = [row for row in rows if row["observation_id"] == observation_id]
    if not previous:
        msg = "Missing observation history; a correction cannot invent the old state."
        raise ValueError(msg)
    latest = max(previous, key=lambda row: int(row["version"]))
    history = append_version(feature_history(previous), units, available_at, status)
    key = tuple(latest[field] for field in DEMAND_GRAIN)
    return [*(dict(row) for row in rows), _source_row(key, observation_id, history[-1])]


def validate_daily_versions(tables: dict) -> int:
    rows = tables[HISTORY_TABLE]
    if len({row["id"] for row in rows}) != len(rows):
        msg = "Duplicate observation history ID."
        raise ValueError(msg)
    grouped = defaultdict(list)
    for row in rows:
        if set(row) != set(HISTORY_COLUMNS) or row["history_policy_version"] != HISTORY_VERSION:
            msg = "Observation history columns/policy disagree."
            raise ValueError(msg)
        grouped[row["observation_id"]].append(row)
    observations = {row["id"]: row for row in tables["daily_demand_observations"]}
    if set(grouped) != set(observations):
        msg = "Missing/extra observation history; absence is not zero."
        raise ValueError(msg)
    for observation_id, versions in grouped.items():
        current = observations[observation_id]
        key = tuple(current[field] for field in DEMAND_GRAIN)
        for row in versions:
            expected = _source_row(
                key,
                observation_id,
                {
                    "version": int(row["version"]),
                    "units_sold": None
                    if row["observed_units"] == ""
                    else int(row["observed_units"]),
                    "observation_status": row["observation_status"],
                    "available_at": row["available_at"],
                },
            )
            if row != expected:
                msg = "Observation history identity/grain disagree."
                raise ValueError(msg)
        history = feature_history(versions)
        close = utc(utc_midnight(date.fromisoformat(current["business_date"]) + timedelta(days=1)))
        if any(utc(version["available_at"]) < close for version in history):
            msg = "Daily history cannot precede day close."
            raise ValueError(msg)
        latest = history[-1]
        if (latest["units_sold"], latest["observation_status"], utc(latest["available_at"])) != (
            None if current["observed_units"] == "" else int(current["observed_units"]),
            current["observation_status"],
            utc(current["available_at"]),
        ):
            msg = "Latest observation history disagrees with current facts."
            raise ValueError(msg)
    return len(rows)


def history_contract_schema() -> dict:
    properties = {field: field_rule(field) for field in HISTORY_COLUMNS}
    properties["version"]["pattern"] = "^[1-9][0-9]*$"
    properties["observed_units"].update(minLength=0, pattern="^(?:0|[1-9][0-9]*)?$")
    properties["observation_status"]["enum"] = [
        "observed_positive",
        "observed_zero",
        "closed",
        "missing",
    ]
    properties["history_policy_version"]["enum"] = [HISTORY_VERSION]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Append-only observed quantity history 1.0.0",
        "type": "object",
        "additionalProperties": False,
        "required": [HISTORY_TABLE],
        "properties": {
            HISTORY_TABLE: {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": HISTORY_COLUMNS,
                    "properties": properties,
                },
            }
        },
    }
