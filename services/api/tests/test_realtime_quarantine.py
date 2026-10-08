from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.realtime_quarantine import replay_quarantined_message


def correction():
    return {
        "event_id": str(uuid4()),
        "event_type": "sale_completed",
        "topic": "retailops.sales.v1",
        "schema_version": "1.0",
        "source": "test",
        "correlation_id": "test",
        "occurred_at": "2026-09-30T10:00:00Z",
        "ingested_at": "2026-09-30T10:00:01Z",
        "payload": {
            "sale_id": "sale-1",
            "product_id": "p1",
            "store_id": "s1",
            "channel": "online",
            "quantity": "2",
            "total_amount": "14",
        },
    }


@pytest.mark.parametrize("failure", ["timeout", "delivery_error", "missing_callback"])
def test_replay_never_confirms_unacknowledged_delivery(failure):
    repository = Mock()
    repository.get.return_value = {"topic": "retailops.sales.v1"}
    repository.prepare_replay.return_value = {"payload": {"replay": {}}}
    producer = Mock()

    def produce(*args, **kwargs):
        if failure == "delivery_error":
            kwargs["on_delivery"](RuntimeError("broker down"), Mock())

    producer.produce.side_effect = produce
    producer.flush.return_value = 1 if failure == "timeout" else 0
    with pytest.raises(RuntimeError, match="delivery receipt"):
        replay_quarantined_message(
            "id",
            event=correction(),
            operator="test",
            bootstrap_servers="broker:9092",
            repository=repository,
            producer=producer,
        )
    repository.prepare_replay.assert_called_once()
    repository.confirm_replay.assert_not_called()


def test_replay_validates_original_route_before_pinning_or_sending():
    repository, producer = Mock(), Mock()
    repository.get.return_value = {"topic": "retailops.inventory.v1"}
    with pytest.raises(ValueError, match="Transport topic mismatch"):
        replay_quarantined_message(
            "id",
            event=correction(),
            operator="test",
            bootstrap_servers="broker:9092",
            repository=repository,
            producer=producer,
        )
    repository.prepare_replay.assert_not_called()
    producer.produce.assert_not_called()


def test_confirmed_replay_is_not_published_again():
    repository, producer = Mock(), Mock()
    repository.get.return_value = {"topic": "retailops.sales.v1"}
    repository.prepare_replay.return_value = {"payload": {"replay": {"delivered_at": "time"}}}
    result = replay_quarantined_message(
        "id",
        event=correction(),
        operator="test",
        bootstrap_servers="broker:9092",
        repository=repository,
        producer=producer,
    )
    assert result["status"] == "already_replayed"
    producer.produce.assert_not_called()
