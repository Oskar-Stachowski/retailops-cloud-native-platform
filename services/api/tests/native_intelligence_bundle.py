"""Read the bounded original AI10 stockout acceptance output; no generated fixture fallback."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from app.services.intelligence_contract import TOPIC, content_hash, validate_event
from app.services.intelligence_model_contract import model_partition_key

MAX_BYTES = 64 * 1024**2
# Exact original frozen primary from the accepted AI07 capsule; never retrain at this boundary.
ANOMALY_MODEL_SHA256 = (
    "febb4393e3d93d6f47bd59d464c245a09315ba6ad18d96e1c186207d1d27af56"
)


def read_regular(path: Path, limit: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("native_acceptance_regular_file_required")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("native_acceptance_byte_limit")
    return raw


def read_census(root: Path, census_id: str) -> tuple[dict, bytes]:
    if re.fullmatch(r"native-model-outbox-sha256-[0-9a-f]{64}", census_id) is None:
        raise ValueError("native_acceptance_census_identity")
    directory = root / "native-outbox" / census_id
    if (root / "native-outbox").is_symlink() or directory.is_symlink():
        raise ValueError("native_acceptance_regular_directory_required")
    receipt = json.loads(read_regular(directory / "receipt.json", 2 * 1024**2))
    if (
        receipt.pop("census_id") != census_id
        or "native-model-outbox-sha256-" + content_hash(receipt) != census_id
    ):
        raise ValueError("native_acceptance_census_identity")
    reference = receipt["events"]
    if (
        receipt["version"] != "native-model-outbox-census-1.0"
        or receipt["environment"] != "test"
        or receipt["topic"] != TOPIC
        or receipt["evidence_class"] != "committed_native_publication_census"
        or reference["path"] != "events.jsonl"
        or type(reference["rows"]) is not int
        or not 1 <= reference["rows"] <= 1400
    ):
        raise ValueError("native_acceptance_census_contract")
    raw = read_regular(directory / "events.jsonl", MAX_BYTES)
    if (
        hashlib.sha256(raw).hexdigest() != reference["sha256"]
        or len(raw) != reference["size_bytes"]
    ):
        raise ValueError("native_acceptance_original_output_binding")
    return receipt, raw


def load_stockout_export(root: Path) -> tuple[dict, tuple[tuple[dict, bytes], ...]]:
    acceptance = json.loads(read_regular(root / "acceptance.json", 64 * 1024))
    census_id = acceptance.get("native_outbox_census_id", "")
    if (
        acceptance.get("status") != "passed"
        or acceptance.get("purpose")
        != "actual_final_model_on_isolated_disposable_runner"
        or not all(
            acceptance.get(name) is True
            for name in (
                "real_public_inputs",
                "real_mlflow",
                "real_postgres",
                "real_cold_worker",
                "actual_HTTP_auth_scope_idempotency",
            )
        )
        or acceptance.get("model_refits") != 0
        or acceptance.get("source_generation") is not False
        or acceptance.get("production_deployed") is not False
        or re.fullmatch(r"[0-9a-f]{40}", str(acceptance.get("commit", ""))) is None
        or re.fullmatch(r"native-model-outbox-sha256-[0-9a-f]{64}", census_id) is None
    ):
        raise ValueError("native_acceptance_genuine_completed_model_required")
    receipt, raw = read_census(root, census_id)
    reference = receipt["events"]
    output_raw = read_regular(root / "native-batch-output.json", MAX_BYTES)
    output = json.loads(output_raw)
    if (
        hashlib.sha256(raw).hexdigest() != reference["sha256"]
        or len(raw) != reference["size_bytes"]
        or hashlib.sha256(output_raw).hexdigest()
        != acceptance["native_batch_output_sha256"]
        or output["output_id"] != acceptance["output_id"]
        or output["run_id"] != acceptance["batch_run_id"]
        or reference["rows"] != acceptance["smoke_rows"]
        or reference["rows"] != acceptance["native_outbox_rows"]
        or len(output["items"]) != reference["rows"]
    ):
        raise ValueError("native_acceptance_original_output_binding")
    expected = {item["risk_id"]: item for item in output["items"]}
    members = {member["event_id"]: member for member in receipt["members"]}
    if len(members) != reference["rows"] or len(expected) != reference["rows"]:
        raise ValueError("native_acceptance_duplicate_census_identity")
    events = []
    seen = set()
    for line in raw.splitlines():
        event = json.loads(line)
        validate_event(event, transport_topic=TOPIC)
        item = event["payload"]
        member = members.get(event["event_id"])
        if (
            event["event_type"] != "stockout_risk_scored"
            or member is None
            or event["event_id"] in seen
            or item != expected.get(item["risk_id"])
            or item["inference_run_id"] != acceptance["batch_run_id"]
            or item["quality_status"] != "passed_at_publication"
            or item["model_name"] != "retailops-stockout-risk"
            or member["event_type"] != event["event_type"]
            or member["result_id"] != item["risk_id"]
            or member["correlation_id"] != event["correlation_id"]
            or member["partition_key"] != model_partition_key(event)
            or member["event_sha256"] != hashlib.sha256(line).hexdigest()
            or member["payload_sha256"] != content_hash(item)
        ):
            raise ValueError("native_acceptance_original_event_binding")
        seen.add(event["event_id"])
        events.append((event, line))
    if len(events) != reference["rows"]:
        raise ValueError("native_acceptance_incomplete_event_census")
    return acceptance, tuple(events)


def load_anomaly_export(root: Path) -> tuple[dict, tuple[tuple[dict, bytes], ...]]:
    report = json.loads(read_regular(root / "acceptance.json", 128 * 1024))
    acceptance = report["acceptance"]
    required_stages = {
        "saved_models_frozen_evaluation_and_current_compatibility",
        "native_complete_public_source_snapshot_dq_coverage_features",
        "actual_built_oci_pinned_pg16_mlflow_and_all_migrations",
        "real_qualified_versions_lifecycle_recovery_atomic_batch_scoped_http",
        "sigkill_restart_preserves_exact_complete_state",
    }
    required_checks = {
        "qualified_primary_promoted_with_actual_image_pin",
        "actual_saved_model_scores_native_verified_public_features",
        "complete_census_atomic_postgresql_publication",
        "native_outbox_insert_failure_rolls_back_complete_batch_request_and_events",
        "scoped_read_api_counts_403_404_and_read_only_routes",
    }
    if (
        report.get("status") != "passed"
        or acceptance.get("status") != "passed"
        or report.get("restart", {}).get("status") != "passed"
        or report.get("qualification_scope") != "synthetic_ai_07_portfolio_v4"
        or report.get("deployment_attestation") != "not_attested"
        or not required_stages <= set(report.get("stages", []))
        or not required_checks <= set(acceptance.get("checks", []))
        or re.fullmatch(r"[0-9a-f]{40}", report.get("consumer_commit", "")) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", report.get("oci_image_digest", ""))
        is None
        or type(report.get("workflow_run_id")) is not int
        or acceptance.get("model_sha256") != ANOMALY_MODEL_SHA256
    ):
        raise ValueError("native_anomaly_genuine_completed_model_required")
    model_raw = read_regular(root / "native-frozen-model.json", 8 * 1024**2)
    if hashlib.sha256(model_raw).hexdigest() != ANOMALY_MODEL_SHA256:
        raise ValueError("native_anomaly_original_model_binding")
    receipt, raw = read_census(root, acceptance["native_outbox_census_id"])
    output_raw = read_regular(root / "native-batch-output.json", MAX_BYTES)
    output = json.loads(output_raw)
    count = receipt["events"]["rows"]
    if (
        hashlib.sha256(output_raw).hexdigest()
        != acceptance["native_batch_output_sha256"]
        or output["batch_id"] != acceptance["batch_id"]
        or len(output["items"]) != count
        or acceptance["native_outbox_rows"] != count
    ):
        raise ValueError("native_anomaly_original_output_binding")
    expected = {item["anomaly_id"]: item for item in output["items"]}
    members = {member["event_id"]: member for member in receipt["members"]}
    if len(expected) != count or len(members) != count:
        raise ValueError("native_anomaly_duplicate_census_identity")
    seen = set()
    events = []
    for line in raw.splitlines():
        event = json.loads(line)
        validate_event(event, transport_topic=TOPIC)
        item = event["payload"]
        member = members.get(event["event_id"])
        if (
            event["event_type"] != "anomaly_detected"
            or member is None
            or event["event_id"] in seen
            or item != expected.get(item["anomaly_id"])
            or item["batch_id"] != acceptance["batch_id"]
            or item["inference_run_id"] != acceptance["batch_id"]
            or item["release_id"] != acceptance["release_id"]
            or item["detector_name"] != "retailops-sales-anomaly"
            or item["quality_status"] != "passed_at_publication"
            or item["source_dataset_id"] != report["source_dataset_id"]
            or item["qualified_anomaly_input_id"]
            != report["qualified_anomaly_input_id"]
            or member["event_type"] != event["event_type"]
            or member["result_id"] != item["anomaly_id"]
            or member["correlation_id"] != event["correlation_id"]
            or member["partition_key"] != model_partition_key(event)
            or member["event_sha256"] != hashlib.sha256(line).hexdigest()
            or member["payload_sha256"] != content_hash(item)
        ):
            raise ValueError("native_anomaly_original_event_binding")
        seen.add(event["event_id"])
        events.append((event, line))
    if len(events) != count:
        raise ValueError("native_anomaly_incomplete_event_census")
    return {
        **acceptance,
        "commit": report["consumer_commit"],
        "workflow_run_id": report["workflow_run_id"],
        "qualification_id": report["qualified_anomaly_input_id"],
    }, tuple(events)
