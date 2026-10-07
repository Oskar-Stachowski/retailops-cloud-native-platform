"""Invented production-shaped payloads and explicit operator attestations, never ML evidence."""

import copy
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4, uuid5

from app.services.intelligence_contract import CONTRACT_DIR, EVENT_NAMESPACE, content_hash
from app.services.intelligence_head_policy import OwnerReviewReceipt
from scripts.prepare_intelligence_head import prepare_policy


def publication_events(
    *,
    products=("fixture-product",),
    locations=("fixture-store",),
    origin=None,
    artifact=None,
    run_id=None,
    horizon=7,
):
    template = json.loads((CONTRACT_DIR / "forecast_generated.fixture.json").read_bytes())
    origin = origin or (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=0,
    )
    artifact = artifact or uuid4().hex * 2
    run_id = run_id or "run-" + uuid4().hex
    result = []
    for product in products:
        for location in locations:
            for day in range(1, horizon + 1):
                event = copy.deepcopy(template)
                payload = event["payload"]
                payload.update(
                    product_id=product,
                    selling_location_id=location,
                    horizon_days=day,
                    model_name="retailops-demand-forecast-v12",
                    inference_run_id=run_id,
                    prediction_dataset_id="v12-forecasts-sha256-" + artifact,
                    forecast_origin=origin.isoformat().replace("+00:00", "Z"),
                    target_date=(origin.date() + timedelta(days=day)).isoformat(),
                    generated_at=(origin + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
                )
                payload["freshness"]["evaluated_at"] = payload["generated_at"]
                key = {
                    name: payload[name]
                    for name in (
                        "product_id",
                        "selling_location_id",
                        "channel",
                        "forecast_origin",
                        "business_timezone",
                        "cutoff_policy",
                        "target_date",
                        "horizon_days",
                    )
                }
                payload["prediction_id"] = "prediction-sha256-" + content_hash(
                    {
                        "projection": "forecast-v12-read-v1",
                        "artifact_id": payload["prediction_dataset_id"],
                        "key": key,
                    }
                )
                event.update(
                    event_id=str(
                        uuid5(EVENT_NAMESPACE, "forecast_generated:" + payload["prediction_id"])
                    ),
                    correlation_id=run_id,
                    occurred_at=payload["generated_at"],
                    ingested_at=payload["generated_at"],
                )
                result.append(event)
    return result


def selected_policy(
    events,
    *,
    products=("fixture-product",),
    locations=("fixture-store",),
    reviewed_at=None,
    horizon=7,
):
    now = reviewed_at or datetime.now(UTC)
    first = events[0]["payload"]
    receipt = OwnerReviewReceipt.model_validate_json(
        json.dumps(
            {
                "model_name": first["model_name"],
                "model_version": first["model_version"],
                "approval_id": "v12-inference-release-sha256-" + "e" * 64,
                "approval_sha256": first["approval_sha256"],
                "rejected": False,
                "release_id": first["release_id"],
                "aliases": {"champion": first["model_version"]},
                "pending_decisions": [],
                "runtime_status": "not_integrated",
            }
        )
    )
    return prepare_policy(
        events,
        products=list(products),
        locations=list(locations),
        horizon=horizon,
        reviewer="invented-fixture-operator",
        owner_review_receipt=receipt,
        reviewed_at=now,
        valid_until=now + timedelta(minutes=5),
    )


def store_policy(path, policy):
    path.write_text(policy.model_dump_json())
    path.chmod(0o600)


def rehash_policy(raw):
    for head in raw["heads"]:
        head["selection_sha256"] = content_hash(
            {key: value for key, value in head.items() if key != "selection_sha256"}
        )
    raw["policy_sha256"] = content_hash(
        {key: value for key, value in raw.items() if key != "policy_sha256"}
    )
    return json.dumps(raw)
