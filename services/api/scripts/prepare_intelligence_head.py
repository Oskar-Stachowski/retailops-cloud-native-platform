"""Prepare an owner-reviewed head policy from a complete private event export; never activate it."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.intelligence_contract import TOPIC, canonical_bytes, content_hash, validate_event
from app.services.intelligence_head import BINDING_FIELDS, MAX_PUBLICATION_BYTES, verify_head_rows
from app.services.intelligence_head_policy import (
    MAX_REVIEW_AGE,
    ApprovedForecastHead,
    ForecastHeadPolicy,
    OwnerReviewReceipt,
    private_document,
)


def prepare_policy(
    events: list[dict[str, Any]],
    *,
    products: list[str],
    locations: list[str],
    horizon: int,
    reviewer: str,
    owner_review_receipt: OwnerReviewReceipt,
    reviewed_at: datetime,
    valid_until: datetime,
) -> ForecastHeadPolicy:
    if not events or len(events) > 1400:
        msg = "head_export_budget"
        raise ValueError(msg)
    for event in events:
        validate_event(event, transport_topic=TOPIC)
    first = events[0]["payload"]
    raw = {
        **{field: first[field] for field in BINDING_FIELDS},
        **{
            field: datetime.fromisoformat(first[field]).isoformat().replace("+00:00", "Z")
            for field in ("forecast_origin", "generated_at", "approval_valid_until")
        },
        "reviewed_by": reviewer,
        "owner_review_receipt_sha256": content_hash(owner_review_receipt.model_dump(mode="json")),
        "owner_review_receipt": owner_review_receipt.model_dump(mode="json"),
        "reviewed_at": reviewed_at.isoformat().replace("+00:00", "Z"),
        "valid_until": valid_until.isoformat().replace("+00:00", "Z"),
        "product_ids": sorted(products),
        "selling_location_ids": sorted(locations),
        "horizon_days": horizon,
        "rows": sorted(
            (
                {
                    "prediction_id": event["payload"]["prediction_id"],
                    "payload_sha256": content_hash(event["payload"]),
                }
                for event in events
            ),
            key=lambda row: row["prediction_id"],
        ),
    }
    raw["selection_sha256"] = content_hash(raw)
    head = ApprovedForecastHead.model_validate_json(canonical_bytes(raw))
    records = {
        event["payload"]["prediction_id"]: {
            "payload": event["payload"],
            "payload_sha256": content_hash(event["payload"]),
        }
        for event in events
    }
    verify_head_rows(head, records)
    policy: dict[str, Any] = {
        "version": "retailops-forecast-head-policy-1.0",
        "heads": [head.model_dump(mode="json")],
    }
    policy["policy_sha256"] = content_hash(policy)
    return ForecastHeadPolicy.model_validate_json(canonical_bytes(policy))


def write_new_policy(path: Path, document: bytes) -> None:
    """Atomic exclusive creation: a pre-existing policy is never replaced by preparation."""
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".forecast-head-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product", action="append", required=True)
    parser.add_argument("--selling-location", action="append", required=True)
    parser.add_argument("--horizon", type=int, choices=(7, 14), required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--owner-review-receipt-file", type=Path, required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--review-seconds", type=int, default=300)
    args = parser.parse_args()
    try:
        if not 1 <= args.review_seconds <= int(MAX_REVIEW_AGE.total_seconds()):
            msg = "head_review_window_invalid"
            raise ValueError(msg)
        events = json.loads(private_document(args.events_file, max_bytes=MAX_PUBLICATION_BYTES))
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            msg = "head_event_array_required"
            raise ValueError(msg)
        now = datetime.now(UTC)
        reviewed_at = datetime.fromisoformat(args.reviewed_at)
        if (
            reviewed_at.tzinfo is None
            or reviewed_at.utcoffset() != timedelta(0)
            or not reviewed_at <= now < reviewed_at + timedelta(seconds=args.review_seconds)
        ):
            msg = "head_review_time_invalid"
            raise ValueError(msg)
        receipt = OwnerReviewReceipt.model_validate_json(
            private_document(args.owner_review_receipt_file, max_bytes=65536)
        )
        policy = prepare_policy(
            events,
            products=args.product,
            locations=args.selling_location,
            horizon=args.horizon,
            reviewer=args.reviewed_by,
            owner_review_receipt=receipt,
            reviewed_at=reviewed_at,
            valid_until=reviewed_at + timedelta(seconds=args.review_seconds),
        )
        write_new_policy(args.output, canonical_bytes(policy.model_dump(mode="json")))
        sys.stdout.write(
            json.dumps(
                {"status": "prepared", "policy_sha256": policy.policy_sha256, "activated": False}
            )
            + "\n"
        )
    except Exception:  # noqa: BLE001 - do not expose private payloads or paths
        sys.stderr.write('{"error":"intelligence_head_preparation_failed"}\n')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
