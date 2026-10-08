"""Truth-blind, bounded replay with explicit progress and immutable daily revisions."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from typing import TYPE_CHECKING

from services.api.app.services.realtime_contract import event_contract

from data.dq.contract import (
    MAX_RECORDS,
    REPLAY_VERSION,
    EventDelivery,
    ProgressDeclaration,
    parse_record,
)
from data.dq.sales import GRAIN, fact_totals, sale_fact
from data.generator.identity import json_sha256
from data.generator.manifest_v2 import unique_keys
from data.inventory.contract import require, utc_timestamp

if TYPE_CHECKING:
    from datetime import datetime


def reject_nonfinite(_value: str) -> None:
    msg = "Nonfinite JSON scalar."
    raise ValueError(msg)


class OfflineReplay:
    """Single selected-sales stream; no DB, broker, ACK or live-consumer mutations."""

    def __init__(self) -> None:
        self.receipts: dict[str, dict] = {}
        self.events: dict[str, str] = {}
        self.business: dict[tuple[str, str], dict] = {}
        self.facts: list[dict] = []
        self.revisions: list[dict] = []
        self.progress: list[dict] = []
        self.quarantine: list[dict] = []
        self.next_offset = 0
        self.last_received: datetime | None = None
        self.max_event_time: datetime | None = None
        self.watermark: datetime | None = None

    def consume(self, payload: dict) -> dict:
        record = parse_record(payload)
        if record.record_id in self.receipts:
            return deepcopy(self.receipts[record.record_id])
        require(len(self.receipts) < MAX_RECORDS, "Offline replay exceeds record budget.")
        received = utc_timestamp(record.received_at)
        require(
            self.last_received is None or received >= self.last_received,
            "Capture delivery time regressed.",
        )
        if isinstance(record, ProgressDeclaration):
            result = self._progress(record)
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

    def _progress(self, record: ProgressDeclaration) -> dict:
        require(
            record.after_offset == self.next_offset - 1,
            "Progress is not at the declared capture position.",
        )
        frontier = utc_timestamp(record.complete_through)
        require(
            self.watermark is None or frontier > self.watermark,
            "Declared watermark did not advance.",
        )
        self.watermark = frontier
        value = {
            "raw_ref": record.record_id,
            "known_at": record.received_at,
            "complete_through": frontier.isoformat(),
            "after_offset": record.after_offset,
            "scope": record.scope,
        }
        self.progress.append(value)
        return {
            "raw_ref": record.record_id,
            "action": "progress",
            "reason": "declared_selected_stream_frontier",
        }

    def _quarantine(self, record: EventDelivery, reason: str) -> dict:
        result = {"raw_ref": record.record_id, "action": "quarantined", "reason": reason}
        self.quarantine.append(
            {
                **result,
                "topic": record.topic,
                "partition": record.partition,
                "offset": record.offset,
                "received_at": record.received_at,
                "body_sha256": hashlib.sha256(record.body_utf8.encode("utf-8")).hexdigest(),
            }
        )
        return result

    def _event(self, record: EventDelivery) -> dict:
        try:
            event = json.loads(
                record.body_utf8, object_pairs_hook=unique_keys, parse_constant=reject_nonfinite
            )
        except (ValueError, TypeError, RecursionError):
            return self._quarantine(record, "invalid_json")
        if (
            isinstance(event, dict)
            and event.get("schema_version") not in event_contract()["supported_schema_versions"]
        ):
            return self._quarantine(record, "unsupported_schema_version")
        try:
            fact = sale_fact(event, record.topic)
        except (ValueError, TypeError, KeyError, ArithmeticError):
            return self._quarantine(record, "invalid_sales_contract")
        if utc_timestamp(fact["ingested_at"]) > utc_timestamp(record.received_at):
            return self._quarantine(record, "fact_unavailable_at_delivery")
        event_hash = json_sha256(event)
        if event["event_id"] in self.events:
            if self.events[event["event_id"]] != event_hash:
                return self._quarantine(record, "event_id_content_conflict")
            return {
                "raw_ref": record.record_id,
                "action": "duplicate_event",
                "reason": "same_event_id_and_content",
            }
        key = fact["source"], fact["sale_id"]
        if key in self.business:
            if self.business[key]["business_version_sha256"] != fact["business_version_sha256"]:
                return self._quarantine(record, "business_revision_requires_explicit_version")
            self.events[event["event_id"]] = event_hash
            return {
                "raw_ref": record.record_id,
                "action": "duplicate_business",
                "reason": "same_business_fact",
            }
        occurred = utc_timestamp(fact["occurred_at"])
        timing = (
            "late"
            if self.watermark is not None and occurred <= self.watermark
            else "out_of_order"
            if self.max_event_time is not None and occurred < self.max_event_time
            else "on_time"
        )
        self.max_event_time = max(self.max_event_time or occurred, occurred)
        self.events[event["event_id"]] = event_hash
        self.business[key] = fact
        accepted = {
            **fact,
            "event_id": event["event_id"],
            "raw_ref": record.record_id,
            "available_at": record.received_at,
            "timing_status": timing,
        }
        self.facts.append(accepted)
        grain = tuple(fact[k] for k in GRAIN)
        same = [r for r in self.facts if tuple(r[k] for k in GRAIN) == grain]
        previous = next(
            (
                r["revision_id"]
                for r in reversed(self.revisions)
                if tuple(r[k] for k in GRAIN) == grain
            ),
            None,
        )
        revision = {
            **fact_totals(same)[0],
            "known_at": record.received_at,
            "source_raw_ref": record.record_id,
            "source_offset": record.offset,
            "previous_revision_id": previous,
            "quality_status": "partial_selected_sales_fixture",
        }
        self.revisions.append(
            {"revision_id": "sales-revision-sha256-" + json_sha256(revision), **revision}
        )
        return {"raw_ref": record.record_id, "action": "accepted", "reason": timing}

    def aggregates_as_of(self, cutoff: str) -> list[dict]:
        """Expose late arrivals only after their captured delivery time."""
        stamp = utc_timestamp(cutoff)
        latest = {}
        for revision in self.revisions:
            if utc_timestamp(revision["known_at"]) <= stamp:
                latest[tuple(revision[k] for k in GRAIN)] = revision
        return deepcopy([latest[k] for k in sorted(latest)])

    def snapshot(self) -> dict:
        counts = Counter(r["action"] for r in self.receipts.values())
        timing = Counter(r["timing_status"] for r in self.facts)
        report = {
            "policy_version": REPLAY_VERSION,
            "status": "completed",
            "scope": "offline_selected_sales_only",
            "input_records": len(self.receipts),
            "raw_events": self.next_offset,
            "accepted": counts["accepted"],
            "duplicate_event": counts["duplicate_event"],
            "duplicate_business": counts["duplicate_business"],
            "quarantined": counts["quarantined"],
            "dlq_fixture": len(self.quarantine),
            "progress_declarations": len(self.progress),
            "late": timing["late"],
            "out_of_order": timing["out_of_order"],
            "aggregate_revisions": len(self.revisions),
            "declared_source_watermark": self.watermark.isoformat() if self.watermark else None,
            "max_accepted_event_time": self.max_event_time.isoformat()
            if self.max_event_time
            else None,
            "watermark_meaning": "explicit_selected_stream_progress_not_curated_completeness",
            "curated_completeness": "not_qualified",
            "transport_durability_proven": False,
        }
        require(
            report["raw_events"]
            == sum(
                counts[k]
                for k in ("accepted", "duplicate_event", "duplicate_business", "quarantined")
            ),
            "Replay reconciliation differs.",
        )
        return deepcopy(
            {
                "report": report,
                "receipts": list(self.receipts.values()),
                "accepted_facts": self.facts,
                "aggregate_revisions": self.revisions,
                "final_aggregates": fact_totals(self.facts),
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
