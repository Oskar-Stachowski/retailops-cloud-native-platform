"""Bind the original model SQL publisher's ACKs to the sealed native output and consumed bytes."""

import hashlib
import re
import time
from uuid import uuid4

from app.services.intelligence_checkpoint import TransportRecord
from app.services.intelligence_contract import TOPIC
from confluent_kafka import Consumer, TopicPartition


def validate_original_receipts(report, acceptance, events, kind):
    expected = {
        event["event_id"]: hashlib.sha256(raw).hexdigest() for event, raw in events
    }
    if (
        report.get("status") != "passed"
        or report.get("original_AI_database_publisher_attested") is not True
        or report.get("producer_commit") != acceptance["commit"]
        or report.get("workflow_run_id") != acceptance["workflow_run_id"]
        or report.get("census_id") != acceptance["native_outbox_census_id"]
        or report.get("model_kind") != kind
        or report.get("delivered") != len(events)
        or len(report.get("receipts", [])) != len(events)
        or len(expected) != len(events)
    ):
        raise ValueError("native_model_original_publisher_complete_binding")
    positions, seen = {}, set()
    for row in report["receipts"]:
        position = row.get("partition"), row.get("offset")
        if (
            row.get("event_id") not in expected
            or row["event_id"] in seen
            or row.get("event_sha256") != expected[row["event_id"]]
            or any(type(value) is not int or value < 0 for value in position)
            or position in positions
            or re.fullmatch(r"[0-9a-f]{64}", str(row.get("wire_sha256", ""))) is None
        ):
            raise ValueError("native_model_original_publisher_receipt_binding")
        seen.add(row["event_id"])
        positions[position] = row["wire_sha256"]
    return positions


def record_fingerprint(message, expected_wire_sha256):
    raw = message.value()
    if (
        message.error() is not None
        or not isinstance(raw, bytes)
        or hashlib.sha256(raw).hexdigest() != expected_wire_sha256
        or message.topic() != TOPIC
    ):
        raise ValueError("native_model_original_consumed_wire_bytes")
    timestamp = message.timestamp()[1]
    return TransportRecord(
        message.partition(),
        message.offset(),
        raw,
        message.key(),
        tuple(message.headers() or ()),
        None if timestamp == -1 else timestamp,
    ).fingerprint()


def verify_original_consumed_records(bootstrap, positions, transport):
    """Read original ACK coordinates without commits; bind value SHA and full SQL fingerprint."""
    stored = {(row[0], row[1]): row[3] for row in transport}
    client = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "ai10-native-wire-" + uuid4().hex,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "error",
            "allow.auto.create.topics": False,
        }
    )
    try:
        for partition in sorted({position[0] for position in positions}):
            offsets = sorted(offset for part, offset in positions if part == partition)
            client.assign([TopicPartition(TOPIC, partition, offsets[0])])
            deadline = time.monotonic() + 30
            for offset in offsets:
                message = None
                while message is None and time.monotonic() < deadline:
                    message = client.poll(0.25)
                if message is None or (message.partition(), message.offset()) != (
                    partition,
                    offset,
                ):
                    raise ValueError("native_model_original_ACK_coordinate_missing")
                fingerprint = record_fingerprint(
                    message, positions[(partition, offset)]
                )
                if stored.get((partition, offset)) != fingerprint:
                    raise ValueError("native_model_original_SQL_transport_fingerprint")
    finally:
        client.close()
