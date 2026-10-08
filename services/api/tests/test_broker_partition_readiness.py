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


@pytest.mark.parametrize(
    "error_code",
    [
        KafkaError.NOT_COORDINATOR,
        KafkaError.COORDINATOR_NOT_AVAILABLE,
        KafkaError.COORDINATOR_LOAD_IN_PROGRESS,
        KafkaError._WAIT_COORD,
    ],
)
def test_committed_observation_waits_for_restarted_coordinator_without_writes(clock, error_code):
    from confluent_kafka import TopicPartition

    expected = [TopicPartition(durability.TOPIC, 0, 4), TopicPartition(durability.TOPIC, 1, 8)]
    replies = iter([KafkaException(KafkaError(error_code)), expected])

    class ReadOnly:
        def committed(self, partitions, *, timeout):
            assert [(p.topic, p.partition) for p in partitions] == [
                (durability.TOPIC, 0),
                (durability.TOPIC, 1),
            ]
            assert 0 < timeout <= 2
            result = next(replies)
            if isinstance(result, Exception):
                raise result
            return result

    assert durability.committed_offsets(ReadOnly()) == expected
    assert clock.now == 0.2


def test_committed_coordinator_observation_has_hard_deadline(clock):
    class Unready:
        def committed(self, partitions, *, timeout):
            raise KafkaException(KafkaError(KafkaError.NOT_COORDINATOR))

    with pytest.raises(pytest.fail.Exception, match="coordinator did not become ready"):
        durability.committed_offsets(Unready(), timeout=0.5)
    assert clock.now == 0.5


def test_committed_authorization_failure_is_never_retried(clock):
    error = KafkaException(KafkaError(KafkaError.GROUP_AUTHORIZATION_FAILED))

    class Denied:
        def committed(self, partitions, *, timeout):
            raise error

    with pytest.raises(KafkaException) as caught:
        durability.committed_offsets(Denied())
    assert caught.value is error and clock.now == 0
