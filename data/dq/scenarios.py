"""Private fault generation and evaluation, separate from the operational reader."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5

from data.dq.contract import GENERATOR_VERSION, KINDS, PLAN_VERSION, TOPIC, FaultPlan, seal_record
from data.dq.replay import OfflineReplay
from data.dq.sales import fact_totals, sale_fact
from data.generator.identity import canonical_json, json_sha256
from data.inventory.contract import require, utc_timestamp

QUARANTINED = frozenset({"unsupported_major", "unsupported_minor", "unexpected_additive_field"})
EXPECTED = {
    "exact_duplicate": ("duplicate_event", "same_event_id_and_content"),
    "business_duplicate": ("duplicate_business", "same_business_fact"),
    "late_event": ("accepted", "late"),
    "out_of_order": ("accepted", "out_of_order"),
    "missing_optional_context": ("accepted", "on_time"),
    "unsupported_major": ("quarantined", "unsupported_schema_version"),
    "unsupported_minor": ("quarantined", "unsupported_schema_version"),
    "unexpected_additive_field": ("quarantined", "invalid_sales_contract"),
}


def private_id(seed: int, kind: str, target: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{GENERATOR_VERSION}:{seed}:{kind}:{target}"))


def example_plan(
    events: list[dict], source_id: str, *, seed: int = 42, limit: int = 256
) -> FaultPlan:
    require(len(events) >= 12, "Example requires twelve source events.")
    dates = [utc_timestamp(e["occurred_at"]).date() for e in events]
    require(dates[0] < dates[-1], "Example late event requires multiple business days.")
    used = {0, len(events) - 1}
    pair = next(
        (
            (i, i + 1)
            for i in range(1, len(events) - 2)
            if dates[i] == dates[i + 1] and events[i]["occurred_at"] < events[i + 1]["occurred_at"]
        ),
        None,
    )
    require(pair is not None, "Example needs two distinct event times on one day.")
    assert pair is not None  # noqa: S101 - narrowed after explicit require
    used.update(pair)
    available = iter(i for i in range(len(events)) if i not in used)
    targets = {"late_event": (0, len(events) - 1), "out_of_order": pair}
    injections = []
    for kind in KINDS:
        target, anchor = targets[kind] if kind in targets else (next(available), None)
        event_id = events[target]["event_id"]
        injections.append(
            {
                "injection_id": private_id(seed, kind, event_id),
                "target_event_id": event_id,
                "issue_type": kind,
                "deliver_after_event_id": events[anchor]["event_id"]
                if anchor is not None
                else None,
            }
        )
    return FaultPlan.from_payload(
        {
            "contract_version": PLAN_VERSION,
            "generator_version": GENERATOR_VERSION,
            "data_class": "simulation_truth",
            "seed": seed,
            "source_dataset_id": source_id,
            "source_events_sha256": json_sha256(events),
            "event_limit": limit,
            "overlap_policy": "reject_target_or_anchor_overlap",
            "injections": injections,
        }
    )


def _tokens(events: list[dict]) -> list[dict]:
    tokens = []
    for index, event in enumerate(events):
        day = utc_timestamp(event["occurred_at"]).date()
        tokens.append({"kind": "event", "event": deepcopy(event), "target": event["event_id"]})
        if (
            index == len(events) - 1
            or utc_timestamp(events[index + 1]["occurred_at"]).date() != day
        ):
            frontier = datetime.combine(day, time.max, tzinfo=UTC).isoformat()
            tokens.append({"kind": "progress", "complete_through": frontier})
    return tokens


def _apply(tokens: list[dict], plan: FaultPlan) -> None:
    for injection in plan.injections:
        index = next(
            i for i, t in enumerate(tokens) if t.get("target") == injection.target_event_id
        )
        token = tokens[index]
        kind = injection.issue_type
        if kind in {"exact_duplicate", "business_duplicate"}:
            token = deepcopy(token)
            token.pop("target")
            if kind == "business_duplicate":
                token["event"]["event_id"] = private_id(
                    plan.seed, "business_envelope", injection.injection_id
                )
            tokens.insert(index + 1, token)
        elif kind in {"late_event", "out_of_order"}:
            token = tokens.pop(index)
            anchor = next(
                i
                for i, t in enumerate(tokens)
                if t.get("target") == injection.deliver_after_event_id
            )
            require(anchor >= index, "DQ delivery anchor must be later in the canonical stream.")
            tokens.insert(anchor + 1, token)
        elif kind == "missing_optional_context":
            require("sku" in token["event"]["payload"], "Optional context is already missing.")
            del token["event"]["payload"]["sku"]
        elif kind in {"unsupported_major", "unsupported_minor"}:
            token["event"]["schema_version"] = "2.0" if kind == "unsupported_major" else "1.1"
        else:
            token["event"]["payload"]["optional_context_v2"] = "future-context"
        token["injection_id"] = injection.injection_id


def capture(events: list[dict], plan: FaultPlan, source_id: str) -> tuple[list[dict], list[dict]]:
    plan = FaultPlan.from_payload(plan.model_dump())
    require(plan.source_dataset_id == source_id, "DQ source identity differs.")
    require(plan.source_events_sha256 == json_sha256(events), "DQ source events differ.")
    require(len(events) <= plan.event_limit, "DQ selection exceeds plan limit.")
    lookup = {e["event_id"]: e for e in events}
    require(len(lookup) == len(events), "Duplicate canonical source event.")
    require(
        events == sorted(events, key=lambda e: (e["occurred_at"], e["payload"]["sale_id"])),
        "Source stream is not canonical.",
    )
    for injection in plan.injections:
        require(injection.target_event_id in lookup, "DQ target missing from source.")
        anchor_id = injection.deliver_after_event_id
        if anchor_id:
            require(anchor_id in lookup, "DQ anchor missing from source.")
            target = utc_timestamp(lookup[injection.target_event_id]["occurred_at"])
            anchor = utc_timestamp(lookup[anchor_id]["occurred_at"])
            require(target < anchor, "DQ anchor does not follow target event time.")
            same_day = target.date() == anchor.date()
            require(
                same_day == (injection.issue_type == "out_of_order"),
                "DQ timing kind does not match watermark scope.",
            )
    tokens = _tokens(events)
    _apply(tokens, plan)
    records, truth = [], []
    previous = datetime.min.replace(tzinfo=UTC)
    offset = 0
    by_id = {i.injection_id: i for i in plan.injections}
    for token in tokens:
        lower = (
            token["event"]["ingested_at"] if token["kind"] == "event" else token["complete_through"]
        )
        received = max(utc_timestamp(lower), previous + timedelta(microseconds=1))
        if token["kind"] == "event":
            record = seal_record(
                {
                    "kind": "event",
                    "topic": TOPIC,
                    "partition": 0,
                    "offset": offset,
                    "received_at": received.isoformat(),
                    "body_utf8": canonical_json(token["event"]).decode("utf-8"),
                }
            )
            offset += 1
        else:
            record = seal_record(
                {
                    "kind": "progress",
                    "scope": "selected_sales_fixture",
                    "after_offset": offset - 1,
                    "received_at": received.isoformat(),
                    "complete_through": token["complete_through"],
                }
            )
        records.append(record)
        previous = received
        if token.get("injection_id"):
            injection = by_id[token["injection_id"]]
            action, reason = EXPECTED[injection.issue_type]
            truth.append(
                {
                    **injection.model_dump(),
                    "raw_ref": record["record_id"],
                    "delivered_event_id": token["event"]["event_id"],
                    "seed": plan.seed,
                    "generator_version": GENERATOR_VERSION,
                    "data_class": "simulation_truth",
                    "occurred_at": token["event"]["occurred_at"],
                    "ingested_at": token["event"]["ingested_at"],
                    "received_at": record["received_at"],
                    "expected_action": action,
                    "expected_reason": reason,
                }
            )
    return records, sorted(truth, key=lambda r: r["injection_id"])


def evaluate(events: list[dict], records: list[dict], truth: list[dict]) -> tuple[dict, dict]:
    reader = OfflineReplay()
    for record in records:
        reader.consume(record)
    result = reader.snapshot()
    for record in records:
        reader.consume(record)
    idempotent = result == reader.snapshot()
    receipts = {r["raw_ref"]: r for r in result["receipts"]}
    outcomes = []
    for injection in truth:
        observed = receipts[injection["raw_ref"]]
        outcomes.append(
            {
                **injection,
                "observed_action": observed["action"],
                "observed_reason": observed["reason"],
                "passed": (observed["action"], observed["reason"])
                == (injection["expected_action"], injection["expected_reason"]),
            }
        )
    excluded = {i["target_event_id"] for i in truth if i["issue_type"] in QUARANTINED}
    expected = [sale_fact(e, TOPIC) for e in events if e["event_id"] not in excluded]
    accepted = result["accepted_facts"]

    def versions(rows: list[dict]) -> list[tuple]:
        return sorted((r["source"], r["sale_id"], r["business_version_sha256"]) for r in rows)

    checks = {
        "all_injections_reconciled": all(r["passed"] for r in outcomes),
        "replay_idempotent": idempotent,
        "accepted_business_facts_match": versions(accepted) == versions(expected),
        "aggregate_reconciliation": result["final_aggregates"] == fact_totals(expected),
        "source_event_accounting": len(expected) + len(excluded) == len(events),
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "data_class": "simulation_truth",
        "injections": outcomes,
        "fault_prevalence": len(truth) / len(events),
        "prevalence_status": "within_recommended_range"
        if 0.005 <= len(truth) / len(events) <= 0.04
        else "bounded_fixture_outside_recommended_range",
        "source_events": len(events),
        "expected_accepted": len(expected),
        "expected_quarantined": len(excluded),
        "offline_only": True,
    }
    require(report["status"] == "passed", "DQ expected/observed reconciliation failed.")
    return result, report
