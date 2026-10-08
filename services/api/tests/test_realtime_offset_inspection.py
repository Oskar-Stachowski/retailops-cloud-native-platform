"""Transient coordinator reads cannot erase or replace durable offset assertions."""

from types import SimpleNamespace

from confluent_kafka import KafkaError, KafkaException
import pytest
import test_realtime_durability as durability


class Client:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0
        self.closed = False

    def committed(self, _partitions, *, timeout):
        assert 0 < timeout <= 2
        self.calls += 1
        if self.errors:
            raise KafkaException(KafkaError(self.errors.pop(0)))
        return [SimpleNamespace(partition=0, offset=17, error=None)]

    def close(self):
        self.closed = True


@pytest.mark.parametrize("code", [KafkaError.NOT_COORDINATOR, KafkaError.COORDINATOR_NOT_AVAILABLE])
def test_transient_coordinator_read_retries_and_returns_only_real_offsets(monkeypatch, code):
    client = Client([code, code])
    monkeypatch.setattr(durability, "build_confluent_kafka_consumer", lambda _context: client)
    monkeypatch.setattr(durability, "config", lambda context: context)
    monkeypatch.setattr(durability.time, "sleep", lambda _seconds: None)
    assert durability.positions(SimpleNamespace()) == {0: 17}
    assert client.calls == 3 and client.closed


def test_permanent_kafka_error_is_not_retried_or_hidden(monkeypatch):
    client = Client([KafkaError.GROUP_AUTHORIZATION_FAILED])
    monkeypatch.setattr(durability, "build_confluent_kafka_consumer", lambda _context: client)
    monkeypatch.setattr(durability, "config", lambda context: context)
    with pytest.raises(KafkaException):
        durability.positions(SimpleNamespace())
    assert client.calls == 1 and client.closed


def test_unavailable_coordinator_has_a_bounded_failure_and_no_invented_offset(monkeypatch):
    client = Client([KafkaError.NOT_COORDINATOR] * 300)
    clock = [0.0]
    monkeypatch.setattr(durability, "build_confluent_kafka_consumer", lambda _context: client)
    monkeypatch.setattr(durability, "config", lambda context: context)
    monkeypatch.setattr(durability.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(durability.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with pytest.raises(pytest.fail.Exception, match="coordinator did not become ready"):
        durability.positions(SimpleNamespace())
    assert client.calls <= 51 and client.closed


@pytest.mark.parametrize(
    "code", [KafkaError.NOT_COORDINATOR, KafkaError.GROUP_AUTHORIZATION_FAILED]
)
def test_partition_error_is_checked_before_an_offset_is_returned(monkeypatch, code):
    client = Client([])
    replies = iter(
        [
            [SimpleNamespace(partition=0, offset=-1, error=KafkaError(code))],
            [SimpleNamespace(partition=0, offset=17, error=None)],
        ]
    )

    def committed(_partitions, *, timeout):
        client.calls += 1
        return next(replies)

    monkeypatch.setattr(client, "committed", committed)
    monkeypatch.setattr(durability, "build_confluent_kafka_consumer", lambda _context: client)
    monkeypatch.setattr(durability, "config", lambda context: context)
    monkeypatch.setattr(durability.time, "sleep", lambda _seconds: None)
    if code == KafkaError.NOT_COORDINATOR:
        assert durability.positions(SimpleNamespace()) == {0: 17}
        assert client.calls == 2
    else:
        with pytest.raises(KafkaException):
            durability.positions(SimpleNamespace())
        assert client.calls == 1
    assert client.closed
