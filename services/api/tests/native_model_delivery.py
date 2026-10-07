"""Bind the original model SQL publisher's ACKs to the sealed native output and consumed bytes."""

import hashlib
import re


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
