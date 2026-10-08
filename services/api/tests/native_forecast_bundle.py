"""Bind every original native v12 event to its complete, committed development publication."""

import hashlib
import json
import re

from app.services.intelligence_contract import TOPIC, content_hash, validate_event
from app.services.intelligence_head_policy import (
    DEVELOPMENT_ACCEPTANCE_SHA256,
    OwnerReviewReceipt,
)
from native_intelligence_bundle import MAX_BYTES, read_regular


def load_forecast_export(root):
    acceptance = json.loads(read_regular(root / "acceptance.json", 128 * 1024))
    if (
        acceptance.get("status") != "passed"
        or acceptance.get("original_quality_status") != "not_ready"
        or acceptance.get("original_quality_reclassified") is not False
        or acceptance.get("model_refits") != 0
        or acceptance.get("production_deployed") is not False
        or acceptance.get("actual_complete_mlflow_http_import_files") != 664
        or acceptance.get("history_days") != 102
        or acceptance.get("rows") != 56
        or not all(
            acceptance.get(name) is True
            for name in (
                "actual_original_full_semantic_verifier",
                "real_postgres",
                "real_frozen_cold_worker",
                "actual_HTTP_auth_scope_idempotency",
                "atomic_outbox_failure_rollback",
            )
        )
        or re.fullmatch(r"[0-9a-f]{40}", acceptance.get("commit", "")) is None
        or type(acceptance.get("workflow_run_id")) is not int
        or acceptance.get("original_manifest_sha256")
        != "29bf6837ca2cb7504213168743239b037041f375763bc8f01ae28c1f6d09b26e"
    ):
        raise ValueError("native_v12_genuine_original_development_acceptance_required")
    raw = read_regular(root / "native-publication.json", MAX_BYTES)
    output = json.loads(raw)
    if (
        hashlib.sha256(raw).hexdigest() != acceptance["native_publication_sha256"]
        or output.pop("artifact_id") != acceptance["publication_id"]
        or "v12-forecasts-sha256-" + content_hash(output)
        != acceptance["publication_id"]
        or output["complete"] is not True
        or output["run_id"] != acceptance["run_id"]
        or output["resolved_model"]["model_name"]
        != "retailops-demand-forecast-v12-development"
        or len(output["rows"]) != 56
    ):
        raise ValueError("native_v12_original_publication_binding")
    decision = output["resolved_model"]["approval"]["qualification"][
        "development_acceptance"
    ]
    if (
        decision["decision"]["sha256"] != DEVELOPMENT_ACCEPTANCE_SHA256
        or decision["original_quality_reclassified"] is not False
        or decision["production_deployment_authorized"] is not False
    ):
        raise ValueError("native_v12_exact_owner_decision_required")
    owner = OwnerReviewReceipt.model_validate_json(
        read_regular(root / "owner-review.json", 64 * 1024)
    )
    expected = {
        (row["product_id"], row["selling_location_id"], row["horizon_days"]): row
        for row in output["rows"]
    }
    raw = read_regular(root / "events.jsonl", MAX_BYTES)
    if hashlib.sha256(raw).hexdigest() != acceptance["events_sha256"]:
        raise ValueError("native_v12_original_event_bytes_changed")
    events, seen, grains = [], set(), set()
    for line in raw.splitlines():
        value = json.loads(line)
        validate_event(value, transport_topic=TOPIC)
        item = value["payload"]
        grain = (
            item["product_id"],
            item["selling_location_id"],
            item["horizon_days"],
        )
        source = expected.get(grain)
        if (
            value["event_type"] != "forecast_generated"
            or value["event_id"] in seen
            or grain in grains
            or source is None
            or item["model_name"] != output["resolved_model"]["model_name"]
            or item["prediction_dataset_id"] != acceptance["publication_id"]
            or item["inference_run_id"] != output["run_id"]
            or item["release_id"] != output["release_id"]
            or item["receipt_id"] != output["receipt_id"]
            or item["model_version"] != owner.model_version
            or item["image_digest"] != output["image_digest"]
            or item["approval_sha256"] != owner.approval_sha256
            or any(item[name] != value for name, value in source.items())
            or any(
                item[name] != output[name]
                for name in (
                    "source_dataset_id",
                    "curated_dataset_id",
                    "feature_set_id",
                    "profile_id",
                    "generated_at",
                )
            )
        ):
            raise ValueError("native_v12_original_functionals_and_lineage_binding")
        seen.add(value["event_id"])
        grains.add(grain)
        events.append((value, line))
    if len(events) != 56 or grains != set(expected):
        raise ValueError("native_v12_complete_native_census_required")
    return acceptance, output, owner, tuple(events)
