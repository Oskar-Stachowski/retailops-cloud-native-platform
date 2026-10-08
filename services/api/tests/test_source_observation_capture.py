"""A capture needs the complete broker prefix including retries absent from SQL delivery receipts."""

import copy
import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from app.services.source_observation_capture import PrefixRecord, seal_capture
from app.services.source_observation_outbox import ObservationError, event_for
from app.services.source_observation_wire import canonical
from test_source_observation_outbox import fact, stream


@pytest.fixture
def census():
    owner = stream()
    first = fact()
    correction = first.model_copy(
        update={
            "id": str(uuid4()),
            "version": 2,
            "observed_units": 4,
            "available_at": first.available_at + timedelta(days=1),
        }
    )
    partition = UUID(first.observation_id).int % 3
    facts, publications = [], []
    for item, offset in ((first, 1), (correction, 2)):
        event = event_for(owner, item)
        raw = canonical(event)
        facts.append(
            {
                "row_id": UUID(item.id),
                "observation_id": UUID(item.observation_id),
                "version": item.version,
                "fact_bytes": canonical(item),
                "fact_sha256": hashlib.sha256(canonical(item)).hexdigest(),
            }
        )
        publications.append(
            {
                "event_id": UUID(event.event_id),
                "observation_id": UUID(item.observation_id),
                "version": item.version,
                "partition": partition,
                "event_bytes": raw,
                "event_sha256": hashlib.sha256(raw).hexdigest(),
                "delivered_offset": offset,
                "delivered_at": item.available_at,
            }
        )
    boundaries = [0, 0, 0]
    boundaries[partition] = 3
    records = tuple(
        PrefixRecord(
            partition,
            offset,
            publications[index]["event_bytes"],
            first.observation_id.encode(),
        )
        for offset, index in ((0, 0), (1, 0), (2, 1))
    )
    return owner, boundaries, facts, publications, records


def test_complete_prefix_keeps_the_retry_that_sql_receipt_does_not_record(census):
    raw = seal_capture(*census)
    captured = json.loads(raw)
    assert len(captured["rows"]) == 2
    assert len(captured["receipts"]) == 3
    assert [receipt["offset"] for receipt in captured["receipts"]] == [0, 1, 2]
    identity = captured.pop("capture_id")
    assert (
        identity
        == "observation-capture-sha256-"
        + hashlib.sha256(
            json.dumps(captured, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert captured["boundaries"] == [
        {"partition": partition, "next_offset": high}
        for partition, high in enumerate(census[1])
    ]


def test_publisher_delivery_offsets_alone_are_not_a_complete_prefix(census):
    owner, boundaries, facts, publications, records = census
    with pytest.raises(ObservationError, match="census_or_budget"):
        seal_capture(owner, boundaries, facts, publications, records[1:])


def test_pending_sql_publication_cannot_be_snapshot_boundary(census):
    owner, boundaries, facts, publications, records = copy.deepcopy(census)
    publications[0]["delivered_offset"] = None
    with pytest.raises(ObservationError, match="pending_or_invalid_outbox"):
        seal_capture(owner, boundaries, facts, publications, records)


def test_poison_or_foreign_raw_bytes_block_capture(census):
    owner, boundaries, facts, publications, records = census
    foreign = PrefixRecord(records[0].partition, 0, b"poison", records[0].key)
    with pytest.raises(ObservationError, match="unknown_broker_record"):
        seal_capture(owner, boundaries, facts, publications, (foreign, *records[1:]))


def test_duplicate_offset_is_not_a_duplicate_business_fact(census):
    owner, boundaries, facts, publications, records = census
    with pytest.raises(ObservationError, match="broker_position_or_key"):
        seal_capture(
            owner, boundaries, facts, publications, (records[0], records[0], records[2])
        )


def test_delivery_receipt_must_bind_its_actual_broker_record(census):
    owner, boundaries, facts, publications, records = copy.deepcopy(census)
    publications[0]["delivered_offset"] = 2
    with pytest.raises(ObservationError, match="delivery_binding"):
        seal_capture(owner, boundaries, facts, publications, records)


def test_missing_original_version_cannot_be_hidden_by_rehashed_outbox(census):
    owner, boundaries, facts, publications, records = census
    with pytest.raises(ObservationError, match="history_gap"):
        seal_capture(owner, boundaries, facts[1:], publications[1:], records)


def test_changed_original_fact_bytes_are_rejected(census):
    owner, boundaries, facts, publications, records = copy.deepcopy(census)
    facts[0]["fact_bytes"] += b"\n"
    with pytest.raises(ObservationError, match="fact_integrity"):
        seal_capture(owner, boundaries, facts, publications, records)
