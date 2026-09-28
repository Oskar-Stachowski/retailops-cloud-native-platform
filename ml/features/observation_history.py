"""Append-only observed quantities and reads at an explicit knowledge cutoff."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

HISTORY_VERSION = "observed-quantity-history-1.0.0"
HISTORY_FIELDS = {"version", "available_at", "units_sold", "observation_status"}
SCORABLE = {"observed_positive", "observed_zero", "complete_zero"}


def utc(value: str | datetime) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        msg = "Observation history requires UTC availability."
        raise ValueError(msg)
    return result


def validate_history(history: list[dict]) -> list[dict]:
    previous = None
    for version, row in enumerate(history, 1):
        if (
            set(row) != HISTORY_FIELDS
            or type(row["version"]) is not int
            or row["version"] != version
        ):
            msg = "Observation history requires contiguous immutable versions."
            raise ValueError(msg)
        available = utc(row["available_at"])
        if previous is not None and available <= previous:
            msg = "Observation history availability must increase strictly."
            raise ValueError(msg)
        previous = available
        status, units = row["observation_status"], row["units_sold"]
        if status == "missing":
            valid = units is None
        else:
            valid = (
                status in {*SCORABLE, "closed"}
                and type(units) is int
                and units >= 0
                and ((units > 0) == (status == "observed_positive"))
            )
        if not valid:
            msg = "Observation history quantity/status disagree."
            raise ValueError(msg)
    return history


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            msg = "Duplicate observation history JSON key."
            raise ValueError(msg)
        result[key] = value
    return result


def read_history(value: str | list[dict]) -> list[dict]:
    history = json.loads(value, object_pairs_hook=_unique_keys) if isinstance(value, str) else value
    if not isinstance(history, list) or not all(isinstance(row, dict) for row in history):
        msg = "Observation history must be a list of versions."
        raise ValueError(msg)
    return validate_history(history)


def history_json(history: list[dict]) -> str:
    return json.dumps(validate_history(history), sort_keys=True, separators=(",", ":"))


def append_version(
    history: list[dict], units: int | None, available_at: str, status: str | None = None
) -> list[dict]:
    validate_history(history)
    status = status or (
        "missing" if units is None else "observed_positive" if units else "observed_zero"
    )
    result = [
        *(dict(version) for version in history),
        {
            "version": len(history) + 1,
            "available_at": utc(available_at).isoformat(),
            "units_sold": units,
            "observation_status": status,
        },
    ]
    return validate_history(result)


def aggregate_versions(
    events: list[tuple[str, datetime, int]], initial_at: datetime | None = None
) -> list[dict]:
    """Apply later revisions of a sale ID as quantity replacements."""
    grouped = defaultdict(list)
    for sale_id, event_available, quantity in events:
        if type(quantity) is not int or quantity < 0:
            msg = "Sale quantity must be a nonnegative integer; unknown is not zero."
            raise ValueError(msg)
        available = utc(event_available)
        grouped[max(available, initial_at) if initial_at is not None else available].append(
            (sale_id, available, quantity)
        )
    if initial_at is not None:
        grouped.setdefault(utc(initial_at), [])
    state, history = {}, []
    for available, updates in sorted(grouped.items()):
        seen = set()
        for sale_id, actual_available, quantity in sorted(
            updates, key=lambda item: (item[1], item[0])
        ):
            key = (sale_id, actual_available)
            if key in seen:
                msg = "Ambiguous sale revision at the same availability."
                raise ValueError(msg)
            seen.add(key)
            state[sale_id] = quantity
        history = append_version(history, sum(state.values()), available.isoformat())
    return history


def observation_at_time(row: dict, cutoff: datetime) -> dict | None:
    cutoff = utc(cutoff)
    if "observation_history" not in row:
        return (
            row
            if row.get("observation_available_at")
            and utc(str(row["observation_available_at"])) <= cutoff
            else None
        )
    history = read_history(row["observation_history"])
    known = [version for version in history if utc(version["available_at"]) <= cutoff]
    if not known:
        return None
    version = known[-1]
    return {
        **row,
        "units_sold": version["units_sold"],
        "observation_status": version["observation_status"],
        "observation_available_at": version["available_at"],
        "observation_history": history_json(known),
    }


def history_status(row: dict, cutoff: datetime) -> str:
    state = observation_at_time(row, cutoff)
    return state["observation_status"] if state is not None else "missing_history"
