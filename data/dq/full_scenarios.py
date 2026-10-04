"""Private v2 faults for each wire type, kept outside the operational stream."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5

from data.dq.contract import KINDS, TOPIC, seal_record
from data.dq.full_contract import (
    CAPTURE_VERSION,
    GENERATOR_VERSION,
    MAX_RECORDS,
    PLAN_VERSION,
    SCOPE,
    FullFaultPlan,
    parse_full_plan,
)
from data.dq.full_replay import FullOfflineReplay, totals
from data.dq.full_source import OPTIONAL_CONTEXT, business_id, parent_facts
from data.dq.scenarios import EXPECTED, QUARANTINED, _tokens
from data.generator.identity import canonical_json, json_sha256
from data.inventory.contract import require, utc_timestamp


def private_id(seed: int, kind: str, target: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{GENERATOR_VERSION}:{seed}:{kind}:{target}"))


def availability_tokens(events: list[dict]) -> list[dict]:
    """Deliver native facts when available; a future return cannot stall sales.

    A frontier waits for every canonical fact through that business day. Faults
    are applied afterwards, so an explicitly held late event still tests a
    correction behind the declared frontier.
    """
    scheduled = []
    days = {}
    for event in events:
        available = utc_timestamp(event["ingested_at"])
        day = utc_timestamp(event["occurred_at"]).date()
        days[day] = max(days.get(day, available), available)
        scheduled.append(
            (
                available,
                0,
                event["event_id"],
                {"kind": "event", "event": deepcopy(event), "target": event["event_id"]},
            )
        )
    known = datetime.min.replace(tzinfo=UTC)
    for day in sorted(days):
        frontier = datetime.combine(day, time.max, tzinfo=UTC)
        known = max(known, frontier, days[day])
        scheduled.append(
            (
                known,
                1,
                day.isoformat(),
                {
                    "kind": "progress",
                    "complete_through": frontier.isoformat(),
                    "scheduled_at": known.isoformat(),
                },
            )
        )
    return [token for _, _, _, token in sorted(scheduled)]


def reorder_pair(subset: list[dict], *, portfolio: bool) -> tuple[int, int] | None:
    return next(
        (
            (i, i + 1)
            for i in range(1, len(subset) - 2)
            if utc_timestamp(subset[i]["occurred_at"]).date()
            == utc_timestamp(subset[i + 1]["occurred_at"]).date()
            and subset[i]["occurred_at"] < subset[i + 1]["occurred_at"]
            and (
                not portfolio
                or (utc_timestamp(subset[i]["ingested_at"]), subset[i]["event_id"])
                < (utc_timestamp(subset[i + 1]["ingested_at"]), subset[i + 1]["event_id"])
            )
        ),
        None,
    )


def example_plan(events: list[dict], source_id: str, *, seed: int = 42) -> FullFaultPlan:
    injections = []
    # A deliberately held/quarantined first purchase makes the entire later
    # return series incomplete. Keep this destructive DQ exercise on a bounded
    # public product scope; selecting it never reads business injection truth.
    fault_product = None
    if len(events) > 4096:
        products = {e["payload"]["product_id"] for e in events}
        eligible = [
            product
            for product in products
            if all(
                len(
                    subset := [
                        e
                        for e in events
                        if e["payload"]["product_id"] == product and e["event_type"] == kind
                    ]
                )
                >= 12
                and reorder_pair(subset, portfolio=True) is not None
                for kind in ("sale_completed", "return_completed")
            )
        ]
        require(bool(eligible), "Portfolio DQ needs a public product with both event types.")
        fault_product = min(
            eligible,
            key=lambda product: (
                sum(e["payload"]["product_id"] == product for e in events),
                product,
            ),
        )
    for event_type in ("sale_completed", "return_completed"):
        subset = [
            e
            for e in events
            if e["event_type"] == event_type
            and (fault_product is None or e["payload"]["product_id"] == fault_product)
        ]
        require(len(subset) >= 12, "Full example requires twelve facts of each type.")
        dates = [utc_timestamp(e["occurred_at"]).date() for e in subset]
        require(dates[0] < dates[-1], "Late example needs multiple event days.")
        used = {0, len(subset) - 1}
        pair = reorder_pair(subset, portfolio=len(events) > 4096)
        require(pair is not None, "Out-of-order example needs two times on the same day.")
        assert pair is not None  # noqa: S101 - explicit require above
        used.update(pair)
        remaining = iter(i for i in range(len(subset)) if i not in used)
        for kind in KINDS:
            target, anchor = (
                (0, len(subset) - 1)
                if kind == "late_event"
                else (pair if kind == "out_of_order" else (next(remaining), None))
            )
            event_id = subset[target]["event_id"]
            injections.append(
                {
                    "injection_id": private_id(seed, kind, event_id),
                    "target_event_id": event_id,
                    "issue_type": kind,
                    "deliver_after_event_id": subset[anchor]["event_id"]
                    if anchor is not None
                    else None,
                }
            )
    return parse_full_plan(
        {
            "contract_version": "raw-dq-plan-2.1.0" if len(events) > 4096 else PLAN_VERSION,
            "generator_version": GENERATOR_VERSION,
            "data_class": "simulation_truth",
            "seed": seed,
            "source_dataset_id": source_id,
            "source_events_sha256": json_sha256(events),
            "event_limit": len(events),
            "overlap_policy": "reject_target_or_anchor_overlap",
            "injections": injections,
        }
    )


def capture(  # noqa: PLR0912, PLR0915 - ordered fault and delivery gates
    events: list[dict], plan: FullFaultPlan, source_id: str
) -> tuple[list[dict], list[dict]]:
    plan = parse_full_plan(plan.model_dump())
    require(plan.source_dataset_id == source_id, "Full DQ source identity differs.")
    require(plan.source_events_sha256 == json_sha256(events), "Full DQ source events differ.")
    require(len(events) == plan.event_limit, "Full plan must cover every canonical fact.")
    require(
        events == sorted(events, key=lambda e: (e["occurred_at"], e["event_type"], business_id(e))),
        "Full source stream is not canonical.",
    )
    lookup = {e["event_id"]: e for e in events}
    require(len(lookup) == len(events), "Repeated canonical source event.")
    portfolio = plan.contract_version == "raw-dq-plan-2.1.0"
    tokens = availability_tokens(events) if portfolio else _tokens(events)
    for injection in plan.injections:
        require(injection.target_event_id in lookup, "Full DQ target absent from source.")
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
            anchor_id = injection.deliver_after_event_id
            require(anchor_id in lookup, "Full DQ anchor absent from source.")
            target_time = utc_timestamp(lookup[injection.target_event_id]["occurred_at"])
            anchor_time = utc_timestamp(lookup[anchor_id]["occurred_at"])
            require(target_time < anchor_time, "DQ anchor does not follow target time.")
            require(
                (target_time.date() == anchor_time.date()) == (kind == "out_of_order"),
                "DQ timing kind differs from frontier scope.",
            )
            token = tokens.pop(index)
            anchor = next(i for i, t in enumerate(tokens) if t.get("target") == anchor_id)
            require(anchor >= index, "Full DQ anchor is not later in the stream.")
            tokens.insert(anchor + 1, token)
        elif kind == "missing_optional_context":
            field = OPTIONAL_CONTEXT[token["event"]["event_type"]]
            require(field in token["event"]["payload"], "Optional context is already absent.")
            del token["event"]["payload"][field]
        elif kind in {"unsupported_major", "unsupported_minor"}:
            token["event"]["schema_version"] = "2.0" if kind == "unsupported_major" else "1.1"
        else:
            token["event"]["payload"]["optional_context_v2"] = "future-context"
        token["injection_id"] = injection.injection_id
    records, truth = [], []
    previous = datetime.min.replace(tzinfo=UTC)
    offset = 0
    by_id = {i.injection_id: i for i in plan.injections}
    frontier = None
    max_event_time = None
    for token in tokens:
        lower = (
            token["event"]["ingested_at"]
            if token["kind"] == "event"
            else token.get("scheduled_at", token["complete_through"])
        )
        received = max(utc_timestamp(lower), previous + timedelta(microseconds=1)).isoformat()
        if token["kind"] == "event":
            payload = {
                "kind": "event",
                "topic": TOPIC,
                "partition": 0,
                "offset": offset,
                "body_utf8": canonical_json(token["event"]).decode(),
            }
            offset += 1
        else:
            payload = {
                "kind": "progress",
                "scope": SCOPE,
                "after_offset": offset - 1,
                "complete_through": token["complete_through"],
            }
        record = seal_record(
            {"contract_version": CAPTURE_VERSION, "received_at": received, **payload}
        )
        records.append(record)
        previous = utc_timestamp(received)
        timing = "on_time"
        if token["kind"] == "progress":
            frontier = utc_timestamp(token["complete_through"])
        else:
            occurred = utc_timestamp(token["event"]["occurred_at"])
            timing = (
                "late"
                if frontier is not None and occurred <= frontier
                else (
                    "out_of_order"
                    if max_event_time is not None and occurred < max_event_time
                    else "on_time"
                )
            )
            issue = by_id[token["injection_id"]].issue_type if token.get("injection_id") else None
            if issue not in QUARANTINED | {"exact_duplicate", "business_duplicate"}:
                max_event_time = max(max_event_time, occurred) if max_event_time else occurred
        if token.get("injection_id"):
            injection = by_id[token["injection_id"]]
            action, reason = EXPECTED[injection.issue_type]
            if portfolio and injection.issue_type == "missing_optional_context":
                reason = timing
            if injection.issue_type == "unexpected_additive_field":
                reason = "invalid_operational_contract"
            truth.append(
                {
                    **injection.model_dump(),
                    "raw_ref": record["record_id"],
                    "event_type": token["event"]["event_type"],
                    "data_class": "simulation_truth",
                    "seed": plan.seed,
                    "generator_version": GENERATOR_VERSION,
                    "expected_action": action,
                    "expected_reason": reason,
                }
            )
    require(len(records) <= MAX_RECORDS, "Full capture exceeds record budget.")
    return records, sorted(truth, key=lambda t: t["injection_id"])


def evaluate(
    tables: dict, source: dict, events: list[dict], records: list[dict], truth: list[dict]
) -> tuple[dict, dict]:
    reader = FullOfflineReplay(tables, source)
    for record in records:
        reader.consume(record)
    result = reader.snapshot()
    for record in records:
        reader.consume(record)
    receipts = {r["raw_ref"]: r for r in result["receipts"]}
    outcomes = [
        {
            **i,
            "observed_action": receipts[i["raw_ref"]]["action"],
            "observed_reason": receipts[i["raw_ref"]]["reason"],
            "passed": (receipts[i["raw_ref"]]["action"], receipts[i["raw_ref"]]["reason"])
            == (i["expected_action"], i["expected_reason"]),
        }
        for i in truth
    ]
    excluded = {i["target_event_id"] for i in truth if i["issue_type"] in QUARANTINED}
    expected = list(
        parent_facts(tables, [e for e in events if e["event_id"] not in excluded]).values()
    )
    checks = {
        "all_injections_reconciled": all(i["passed"] for i in outcomes),
        "replay_idempotent": result == reader.snapshot(),
        "accepted_business_facts_match": sorted(f["business_version_sha256"] for f in expected)
        == sorted(f["business_version_sha256"] for f in result["accepted_facts"]),
        "aggregate_reconciliation": result["final_aggregates"] == totals(expected),
        "source_event_accounting": len(expected) + len(excluded) == len(events),
        "missing_parent_facts_reconciled": result["report"]["missing_parent_facts"]
        == len(excluded),
    }
    require(all(checks.values()), "Full DQ expected/observed reconciliation failed.")
    return result, {
        "status": "passed",
        "data_class": "simulation_truth",
        "checks": checks,
        "injections": outcomes,
        "source_events": len(events),
        "expected_accepted": len(expected),
        "expected_quarantined": len(excluded),
        "fault_prevalence": len(truth) / len(events),
        "offline_only": True,
    }
