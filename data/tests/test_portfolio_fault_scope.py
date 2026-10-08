"""Destructive faults must exercise DQ without erasing every business series."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from data.dq.full_scenarios import example_plan


def public_events():
    rows = []
    for product, count in (("bounded", 16), ("large", 2100)):
        for event_type in ("sale_completed", "return_completed"):
            for number in range(count):
                stamp = datetime(2026, 3, 26, tzinfo=UTC) + timedelta(
                    days=number // 8, minutes=number % 8
                )
                rows.append({
                    "event_id": str(uuid5(NAMESPACE_URL, f"{product}/{event_type}/{number}")),
                    "event_type": event_type,
                    "occurred_at": stamp.isoformat(),
                    "ingested_at": (stamp + timedelta(minutes=1)).isoformat(),
                    "payload": {"product_id": product},
                })
    return sorted(rows, key=lambda e: (e["occurred_at"], e["event_type"], e["event_id"]))


def test_portfolio_faults_leave_other_public_product_history_intact():
    # This input contains only native public facts, with no scenario or labels.
    events = public_events()
    source = "source-sha256-" + "1" * 64
    plan = example_plan(events, source)
    lookup = {e["event_id"]: e for e in events}
    assert plan.contract_version == "raw-dq-plan-2.1.0"
    assert len(plan.injections) == 16
    assert {lookup[i.target_event_id]["payload"]["product_id"] for i in plan.injections} == {
        "bounded"
    }
    assert {
        lookup[i.deliver_after_event_id]["payload"]["product_id"]
        for i in plan.injections if i.deliver_after_event_id
    } == {"bounded"}
    assert plan == example_plan(events, source)
    changed = [e for e in events if e["payload"]["product_id"] == "large"]
    legacy = example_plan(changed[:32], source)
    assert legacy.contract_version == "raw-dq-plan-2.0.0"
