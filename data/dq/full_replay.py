"""Truth-blind full replay qualified against canonical operational parent facts."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from decimal import Decimal

from services.api.app.services.realtime_contract import event_contract

from data.dq.full_contract import (
    MAX_RECORDS,
    REPLAY_VERSION,
    SCOPE,
    FullEventDelivery,
    FullProgressDeclaration,
    parse_record,
)
from data.dq.full_source import GRAIN, business_id, full_events, match_fact, parent_facts
from data.dq.replay import reject_nonfinite
from data.generator.identity import json_sha256
from data.generator.manifest_v2 import unique_keys
from data.inventory.contract import require, utc_timestamp


def finite_float(value: str) -> float:
    number = float(value)
    require(math.isfinite(number), "Nonfinite JSON scalar.")
    return number


def totals(facts: list[dict]) -> list[dict]:
    grouped = {}
    for fact in facts:
        key = tuple(fact[k] for k in GRAIN)
        row = grouped.setdefault(
            key,
            {
                **dict(zip(GRAIN, key, strict=True)),
                "fact_count": 0,
                "claim_units": 0,
                "units": 0,
                "rejected_units": 0,
                "amount": "0.00",
                "stock_location_ids": set(),
            },
        )
        row["fact_count"] += 1
        row["claim_units"] += fact["quantity"]
        row["units"] += fact["quantity"] if fact["status"] != "rejected" else 0
        row["rejected_units"] += fact["quantity"] if fact["status"] == "rejected" else 0
        row["amount"] = f"{Decimal(row['amount']) + Decimal(fact['amount']):.2f}"
        row["stock_location_ids"].add(fact["stock_location_id"])
    return [
        {**grouped[k], "stock_location_ids": sorted(grouped[k]["stock_location_ids"])}
        for k in sorted(grouped)
    ]


class FullOfflineReplay:
    """Operational parent only; private fault plans and labels are never inputs."""

    def __init__(self, tables: dict, manifest: dict) -> None:
        events = full_events(tables, manifest)
        self.canonical = {(e["event_type"], business_id(e)): deepcopy(e) for e in events}
        self.parent = parent_facts(tables, events)
        self.canonical_ids = {e["event_id"]: (e["event_type"], business_id(e)) for e in events}
        require(
            len(self.canonical) == len(events) == len(self.canonical_ids), "Repeated parent fact."
        )
        self.receipts: dict[str, dict] = {}
        self.events: dict[str, str] = {}
        self.business: dict[tuple[str, str], dict] = {}
        self.facts: list[dict] = []
        self.revisions: list[dict] = []
        self.progress: list[dict] = []
        self.quarantine: list[dict] = []
        self.next_offset = 0
        self.last_received = None
        self.max_event_time = None
        self.watermark = None

    def consume(self, payload: dict) -> dict:
        record = parse_record(payload)
        if record.record_id in self.receipts:
            return deepcopy(self.receipts[record.record_id])
        require(len(self.receipts) < MAX_RECORDS, "Full replay exceeds record budget.")
        received = utc_timestamp(record.received_at)
        require(
            self.last_received is None or received >= self.last_received,
            "Capture delivery time regressed.",
        )
        if isinstance(record, FullProgressDeclaration):
            require(
                record.after_offset == self.next_offset - 1, "Progress capture position differs."
            )
            frontier = utc_timestamp(record.complete_through)
            require(
                self.watermark is None or frontier > self.watermark,
                "Declared watermark did not advance.",
            )
            self.watermark = frontier
            self.progress.append(
                {
                    "raw_ref": record.record_id,
                    "known_at": record.received_at,
                    "complete_through": record.complete_through,
                    "after_offset": record.after_offset,
                    "scope": record.scope,
                }
            )
            result = {
                "raw_ref": record.record_id,
                "action": "progress",
                "reason": "declared_parent_stream_frontier",
            }
        else:
            require(
                record.offset == self.next_offset,
                "Capture offsets are not contiguous or were rewritten.",
            )
            result = self._event(record)
            self.next_offset += 1
        self.last_received = received
        self.receipts[record.record_id] = result
        return deepcopy(result)

    def _quarantine(self, record: FullEventDelivery, reason: str) -> dict:
        result = {"raw_ref": record.record_id, "action": "quarantined", "reason": reason}
        self.quarantine.append(
            {
                **result,
                "topic": record.topic,
                "partition": record.partition,
                "offset": record.offset,
                "received_at": record.received_at,
                "body_sha256": hashlib.sha256(record.body_utf8.encode()).hexdigest(),
            }
        )
        return result

    def _event(self, record: FullEventDelivery) -> dict:
        try:
            event = json.loads(
                record.body_utf8,
                object_pairs_hook=unique_keys,
                parse_constant=reject_nonfinite,
                parse_float=finite_float,
            )
            event_hash = json_sha256(event)
        except (ValueError, TypeError, RecursionError, UnicodeError):
            return self._quarantine(record, "invalid_json")
        if (
            isinstance(event, dict)
            and event.get("schema_version") not in event_contract()["supported_schema_versions"]
        ):
            return self._quarantine(record, "unsupported_schema_version")
        if (
            isinstance(event, dict)
            and isinstance(event.get("event_id"), str)
            and event["event_id"] in self.events
        ):
            if self.events[event["event_id"]] != event_hash:
                return self._quarantine(record, "event_id_content_conflict")
            return {
                "raw_ref": record.record_id,
                "action": "duplicate_event",
                "reason": "same_event_id_and_content",
            }
        try:
            fact = match_fact(event, self.canonical, self.parent)
            key = event["event_type"], business_id(event)
            require(
                event["event_id"] not in self.canonical_ids
                or self.canonical_ids[event["event_id"]] == key,
                "Canonical event ID identifies a different fact.",
            )
        except (ValueError, TypeError, KeyError, ArithmeticError):
            return self._quarantine(record, "invalid_operational_contract")
        if utc_timestamp(fact["ingested_at"]) > utc_timestamp(record.received_at):
            return self._quarantine(record, "fact_unavailable_at_delivery")
        self.events[event["event_id"]] = event_hash
        if key in self.business:
            return {
                "raw_ref": record.record_id,
                "action": "duplicate_business",
                "reason": "same_business_fact",
            }
        occurred = utc_timestamp(fact["occurred_at"])
        timing = (
            "late"
            if self.watermark is not None and occurred <= self.watermark
            else (
                "out_of_order"
                if self.max_event_time is not None and occurred < self.max_event_time
                else "on_time"
            )
        )
        self.max_event_time = max(self.max_event_time or occurred, occurred)
        self.business[key] = fact
        self.facts.append(
            {
                **fact,
                "event_id": event["event_id"],
                "raw_ref": record.record_id,
                "available_at": record.received_at,
                "timing_status": timing,
            }
        )
        grain = tuple(fact[k] for k in GRAIN)
        same = [f for f in self.facts if tuple(f[k] for k in GRAIN) == grain]
        previous = next(
            (
                r["revision_id"]
                for r in reversed(self.revisions)
                if tuple(r[k] for k in GRAIN) == grain
            ),
            None,
        )
        revision = {
            **totals(same)[0],
            "known_at": record.received_at,
            "source_raw_ref": record.record_id,
            "source_offset": record.offset,
            "previous_revision_id": previous,
            "quality_status": "partial_parent_fact_coverage",
            "business_event_day_completeness": "not_qualified",
        }
        self.revisions.append(
            {"revision_id": "operational-revision-sha256-" + json_sha256(revision), **revision}
        )
        return {"raw_ref": record.record_id, "action": "accepted", "reason": timing}

    def aggregates_as_of(self, cutoff: str) -> list[dict]:
        stamp = utc_timestamp(cutoff)
        latest = {}
        for revision in self.revisions:
            if utc_timestamp(revision["known_at"]) <= stamp:
                latest[tuple(revision[k] for k in GRAIN)] = revision
        return deepcopy([latest[k] for k in sorted(latest)])

    def coverage(self) -> list[dict]:
        grouped = {}
        for key, fact in self.parent.items():
            grain = tuple(fact[k] for k in GRAIN)
            row = grouped.setdefault(
                grain,
                {
                    **dict(zip(GRAIN, grain, strict=True)),
                    "expected_parent_facts": 0,
                    "accepted_parent_facts": 0,
                    "missing_business_ids": [],
                },
            )
            row["expected_parent_facts"] += 1
            if key in self.business:
                row["accepted_parent_facts"] += 1
            else:
                row["missing_business_ids"].append(key[1])
        return [
            {
                **grouped[k],
                "missing_business_ids": sorted(grouped[k]["missing_business_ids"]),
                "status": "incomplete_parent_fact_coverage"
                if grouped[k]["missing_business_ids"]
                else "complete_parent_fact_coverage",
                "business_event_day_completeness": "not_qualified",
            }
            for k in sorted(grouped)
        ]

    def snapshot(self) -> dict:
        counts = Counter(r["action"] for r in self.receipts.values())
        timing = Counter(r["timing_status"] for r in self.facts)
        accepted_types = Counter(r["event_type"] for r in self.facts)
        require(
            self.next_offset
            == sum(
                counts[k]
                for k in ("accepted", "duplicate_event", "duplicate_business", "quarantined")
            ),
            "Full replay accounting differs.",
        )
        return deepcopy(
            {
                "report": {
                    "policy_version": REPLAY_VERSION,
                    "status": "completed",
                    "scope": SCOPE,
                    "input_records": len(self.receipts),
                    "raw_events": self.next_offset,
                    **{
                        k: counts[k]
                        for k in (
                            "accepted",
                            "duplicate_event",
                            "duplicate_business",
                            "quarantined",
                        )
                    },
                    "accepted_sales": accepted_types["sale_completed"],
                    "accepted_return_claims": accepted_types["return_completed"],
                    "missing_parent_facts": len(self.parent) - len(self.business),
                    "late": timing["late"],
                    "out_of_order": timing["out_of_order"],
                    "aggregate_revisions": len(self.revisions),
                    "progress_declarations": len(self.progress),
                    "declared_source_watermark": self.watermark.isoformat()
                    if self.watermark
                    else None,
                    "max_accepted_event_time": self.max_event_time.isoformat()
                    if self.max_event_time
                    else None,
                    "watermark_meaning": "explicit_parent_stream_progress_not_business_event_day_completeness",
                    "curated_completeness": "not_qualified",
                    "missing_grain_policy": "unknown_not_zero",
                    "transport_durability_proven": False,
                },
                "receipts": list(self.receipts.values()),
                "accepted_facts": self.facts,
                "aggregate_revisions": self.revisions,
                "final_aggregates": totals(self.facts),
                "parent_fact_coverage": self.coverage(),
                "progress": self.progress,
                "quarantine": self.quarantine,
                "dlq_fixture": [
                    {
                        "target": "retailops.dlq.v1",
                        "raw_ref": r["raw_ref"],
                        "reason": r["reason"],
                        "status": "offline_only",
                    }
                    for r in self.quarantine
                ],
            }
        )
