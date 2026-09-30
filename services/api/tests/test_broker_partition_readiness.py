"""Regression checks for partition recovery during real-broker fixture setup."""

from types import SimpleNamespace

from confluent_kafka import KafkaError, KafkaException
import pytest

import test_realtime_durability as durability


@pytest.fixture
def clock(monkeypatch):
    state = SimpleNamespace(now=0.0)
    monkeypatch.setattr(durability.time, "monotonic", lambda: state.now)

    def sleep(seconds):
        state.now += seconds

    monkeypatch.setattr(durability.time, "sleep", sleep)
    return state


@pytest.mark.parametrize(
    "error_code",
    [KafkaError.NOT_LEADER_FOR_PARTITION, KafkaError.LEADER_NOT_AVAILABLE, KafkaError._TIMED_OUT],
)
def test_offsets_wait_for_both_partitions_before_commit(monkeypatch, clock, error_code):
    calls = []
    replies = iter([(0, 4), KafkaException(KafkaError(error_code)), (0, 6), (0, 8)])

    class Client:
        def get_watermark_offsets(self, partition, *, timeout, cached):
            calls.append(("read", partition.partition, cached))
            assert 0 < timeout <= 2
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply

        def commit(self, *, offsets, asynchronous):
            calls.append(("commit", [(p.partition, p.offset) for p in offsets], asynchronous))

        def close(self):
            calls.append(("close",))

    monkeypatch.setattr(durability, "Consumer", lambda _: Client())
    runtime = SimpleNamespace(db="isolated-test-db", bootstrap="isolated-broker")
    durability.context.__wrapped__(runtime, monkeypatch)
    assert calls == [
        ("read", 0, False),
        ("read", 1, False),
        ("read", 0, False),
        ("read", 1, False),
        ("commit", [(0, 6), (1, 8)], False),
        ("close",),
    ]
    assert clock.now == 0.2


def test_partition_read_failure_stops_at_deadline(clock):
    class Unready:
        def get_watermark_offsets(self, partition, *, timeout, cached):
            raise KafkaException(KafkaError(KafkaError.NOT_LEADER_FOR_PARTITION))

    with pytest.raises(pytest.fail.Exception, match="partition reads did not become ready"):
        durability.initial_offsets(Unready(), timeout=0.5)
    assert clock.now == 0.5


def test_missing_watermark_result_never_becomes_an_initial_offset(clock):
    class TimedOut:
        def get_watermark_offsets(self, partition, *, timeout, cached):
            return None

    with pytest.raises(pytest.fail.Exception, match="offset query timed out"):
        durability.initial_offsets(TimedOut(), timeout=0.5)
    assert clock.now == 0.5


def test_authorization_failure_is_not_retried(clock):
    error = KafkaException(KafkaError(KafkaError.TOPIC_AUTHORIZATION_FAILED))

    class Unauthorized:
        def get_watermark_offsets(self, partition, *, timeout, cached):
            raise error

    with pytest.raises(KafkaException) as caught:
        durability.initial_offsets(Unauthorized())
    assert caught.value is error
    assert clock.now == 0
