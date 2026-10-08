"""Native availability must not be serialized behind a delayed return."""

from data.dq.full_scenarios import availability_tokens


def test_delayed_return_does_not_postpone_available_sale_and_frontier_waits():
    events = [
        {"event_id": "return", "occurred_at": "2026-06-02T09:00:00Z",
         "ingested_at": "2026-06-04T04:00:00Z"},
        {"event_id": "sale", "occurred_at": "2026-06-02T09:01:00Z",
         "ingested_at": "2026-06-02T09:02:00Z"},
        {"event_id": "next-sale", "occurred_at": "2026-06-03T09:01:00Z",
         "ingested_at": "2026-06-03T09:02:00Z"},
    ]
    tokens = availability_tokens(events)
    assert [t["target"] for t in tokens if t["kind"] == "event"] == [
        "sale", "next-sale", "return"
    ]
    frontiers = [t for t in tokens if t["kind"] == "progress"]
    assert frontiers[0]["complete_through"] == "2026-06-02T23:59:59.999999+00:00"
    assert frontiers[0]["scheduled_at"] == "2026-06-04T04:00:00+00:00"
    assert frontiers[1]["scheduled_at"] == frontiers[0]["scheduled_at"]
    assert tokens.index(frontiers[0]) > next(i for i,t in enumerate(tokens) if t.get("target") == "return")
    assert availability_tokens(events) == tokens
