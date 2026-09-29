"""The published v1 contract must match every active producer and route."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest

from app.core.config import DEFAULT_BROKER_TOPICS
from app.services.realtime_contract import EVENT_TOPICS, event_contract, event_validator, validate_event
from app.services.realtime_consumer import RealtimeEventEnvelope
from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.realtime import (
    EVENT_TOPICS as GENERATOR_TOPICS,
)
from data.generator.realtime import (
    RealtimeEventGenerationConfig,
    _event,
    build_realtime_events,
)
from scripts.generate_observability_demo_events import build_events

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def events() -> list[dict]:
    dataset = DatasetGenerationConfig(
        profile="small", days=7, products=3, stores=2, warehouses=1, seed=42
    )
    return build_realtime_events(
        build_dataset(dataset), RealtimeEventGenerationConfig(dataset=dataset, max_events=None)
    )


def test_all_generated_and_demo_events_validate_against_schema(events: list[dict]) -> None:
    assert {event["event_type"] for event in events} == set(EVENT_TOPICS)
    assert GENERATOR_TOPICS == EVENT_TOPICS == event_contract()["event_type_topics"]
    for event in events:
        validate_event(event, transport_topic=event["topic"])

    demo = build_events(
        [{"id": str(i), "sku": f"SKU-{i}", "name": f"Product {i}", "category": "test"}
         for i in range(3)]
    )
    for event in demo:
        if event["event_type"] in EVENT_TOPICS:
            validate_event(event, transport_topic=event["topic"])


def test_registry_matches_broker_initializers_and_default_subscriptions() -> None:
    topics = set(EVENT_TOPICS.values())
    assert topics == set(DEFAULT_BROKER_TOPICS)
    for filename in ("docker-compose.yml", "k8s/overlays/dev/broker/topic-init-job.yaml"):
        body = (ROOT / filename).read_text()
        loop = re.search(r"for topic in(?P<names>.*?)\n\s*do\b", body, re.DOTALL)
        assert loop is not None, filename
        names = re.findall(r"retailops\.[a-z.0-9]+", loop["names"])
        assert len(names) == len(topics) + 1, filename
        assert set(names) == topics | {"retailops.dlq.v1"}, filename

    smoke = (ROOT / "scripts/ci/streaming_smoke.sh").read_text()
    declared = re.search(r"expected_topics=\((?P<names>.*?)\)", smoke, re.DOTALL)
    assert declared is not None
    assert set(re.findall(r"retailops\.[a-z.0-9]+", declared["names"])) == topics | {
        "retailops.dlq.v1"
    }


@pytest.mark.parametrize(
    ("mutation", "transport"),
    [
        ({"topic": None}, None),
        ({"topic": "retailops.inventory.v1"}, None),
        ({}, "retailops.inventory.v1"),
        ({"schema_version": "2.0"}, None),
        ({"schema_version": "1.1"}, None),
        ({"event_type": "future_event"}, None),
        ({"payload": {}}, None),
        ({"payload": {"product_id": "product-1"}}, None),
        ({"payload": []}, None),
        ({"payload": {"product_id": "product-1", "store_id": "store-1", "channel": "online",
                      "quantity": "not-a-number", "total_amount": "14"}}, None),
    ],
)
def test_invalid_envelope_route_version_or_payload_is_rejected(
    events: list[dict], mutation: dict, transport: str | None
) -> None:
    sample = deepcopy(next(event for event in events if event["event_type"] == "sale_completed"))
    sample.update(mutation)
    with pytest.raises((ValueError, TypeError)):
        RealtimeEventEnvelope.from_dict(sample, transport_topic=transport)


def test_unknown_payload_field_is_not_accepted_as_an_unreviewed_minor_change(
    events: list[dict],
) -> None:
    sample = deepcopy(next(event for event in events if event["event_type"] == "sale_completed"))
    sample["payload"]["future_model_label"] = "oracle"
    with pytest.raises(ValueError):
        validate_event(sample)


@pytest.mark.parametrize("event_type", sorted(EVENT_TOPICS))
def test_each_payload_schema_requires_its_own_business_fields(
    events: list[dict], event_type: str
) -> None:
    sample = deepcopy(next(event for event in events if event["event_type"] == event_type))
    schema = event_validator().schema["$defs"][event_type]
    sample["payload"].pop(schema["required"][0])
    with pytest.raises(ValueError):
        validate_event(sample, transport_topic=sample["topic"])


def test_generated_identity_is_stable_for_replay_and_changes_for_new_revision() -> None:
    kwargs = {
        "seed": 42,
        "source": "retailops.synthetic-generator",
        "event_type": "sale_completed",
        "natural_key": "sale-1",
        "correlation_id": "order-1",
        "occurred_at": "2026-05-07T10:15:30+00:00",
        "ingested_at": "2026-05-07T10:15:31+00:00",
        "payload": {"product_id": "product-1", "store_id": "store-1", "channel": "online",
                    "quantity": "2", "total_amount": "14"},
    }
    first = _event(**kwargs)
    assert first == _event(**kwargs)
    revised = _event(**{**kwargs, "payload": {**kwargs["payload"], "quantity": "3"}})
    later = _event(**{**kwargs, "ingested_at": "2026-05-07T11:15:31+00:00"})
    assert len({first["event_id"], revised["event_id"], later["event_id"]}) == 3


def test_contrasting_snapshots_never_reuse_id_for_changed_content() -> None:
    snapshots = []
    for products in (3, 4):
        dataset = DatasetGenerationConfig(
            profile="small", days=7, products=products, stores=2, warehouses=1, seed=42
        )
        snapshots.append(
            build_realtime_events(
                build_dataset(dataset),
                RealtimeEventGenerationConfig(dataset=dataset, max_events=None),
            )
        )
    first = {event["event_id"]: event for event in snapshots[0]}
    assert len(first) == len(snapshots[0])
    assert not [
        event for event in snapshots[1]
        if event["event_id"] in first and event != first[event["event_id"]]
    ]
