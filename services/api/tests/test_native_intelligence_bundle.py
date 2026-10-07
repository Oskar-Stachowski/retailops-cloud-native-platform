"""Mechanics fixtures and damaged export receipts cannot supply genuine native acceptance."""

import hashlib
import json

import pytest
from app.services.intelligence_contract import CONTRACT_DIR, content_hash
from app.services.intelligence_model_contract import model_partition_key
from native_intelligence_bundle import load_stockout_export


@pytest.fixture
def mechanics_export(tmp_path):
    event = json.loads(
        (CONTRACT_DIR / "stockout_risk_scored.fixture.json").read_bytes()
    )
    item = event["payload"]
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    body = {
        "version": "native-model-outbox-census-1.0",
        "environment": "test",
        "topic": event["topic"],
        "evidence_class": "committed_native_publication_census",
        "events": {
            "path": "events.jsonl",
            "rows": 1,
            "size_bytes": len(raw) + 1,
            "sha256": hashlib.sha256(raw + b"\n").hexdigest(),
        },
        "members": [
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "result_id": item["risk_id"],
                "correlation_id": event["correlation_id"],
                "partition_key": model_partition_key(event),
                "event_sha256": hashlib.sha256(raw).hexdigest(),
                "payload_sha256": content_hash(item),
            }
        ],
    }
    census_id = "native-model-outbox-sha256-" + content_hash(body)
    body["census_id"] = census_id
    directory = tmp_path / "native-outbox" / census_id
    directory.mkdir(parents=True)
    (directory / "receipt.json").write_text(json.dumps(body))
    (directory / "events.jsonl").write_bytes(raw + b"\n")
    output = {
        "output_id": "stockout-output-sha256-" + "a" * 64,
        "run_id": item["inference_run_id"],
        "items": [item],
    }
    output_raw = json.dumps(output).encode()
    (tmp_path / "native-batch-output.json").write_bytes(output_raw)
    # All documentary claims here are deliberately synthetic. The original native
    # namespace/quality remains mechanics, so even these claims must not suffice.
    acceptance = {
        "status": "passed",
        "purpose": "actual_final_model_on_isolated_disposable_runner",
        "real_public_inputs": True,
        "real_mlflow": True,
        "real_postgres": True,
        "real_cold_worker": True,
        "actual_HTTP_auth_scope_idempotency": True,
        "model_refits": 0,
        "source_generation": False,
        "production_deployed": False,
        "commit": "a" * 40,
        "native_outbox_census_id": census_id,
        "output_id": output["output_id"],
        "batch_run_id": output["run_id"],
        "smoke_rows": 1,
        "native_outbox_rows": 1,
        "native_batch_output_sha256": hashlib.sha256(output_raw).hexdigest(),
    }
    (tmp_path / "acceptance.json").write_text(json.dumps(acceptance))
    return tmp_path, acceptance, directory


def test_mechanics_payload_cannot_be_qualified_by_documentary_claims(mechanics_export):
    root, _, _ = mechanics_export
    with pytest.raises(ValueError, match="original_event_binding"):
        load_stockout_export(root)


@pytest.mark.parametrize(
    "field",
    [
        "real_public_inputs",
        "real_mlflow",
        "real_postgres",
        "real_cold_worker",
        "actual_HTTP_auth_scope_idempotency",
    ],
)
def test_all_actual_runtime_preconditions_are_required(mechanics_export, field):
    root, acceptance, _ = mechanics_export
    acceptance[field] = False
    (root / "acceptance.json").write_text(json.dumps(acceptance))
    with pytest.raises(ValueError, match="genuine_completed_model_required"):
        load_stockout_export(root)


@pytest.mark.parametrize(
    "file", ["events.jsonl", "receipt.json", "native-batch-output.json"]
)
def test_rehashed_or_replaced_receipts_are_rejected(mechanics_export, file):
    root, _, directory = mechanics_export
    path = root / file if file == "native-batch-output.json" else directory / file
    value = path.read_bytes()
    if file == "events.jsonl":
        value += b"\n"
    else:
        document = json.loads(value)
        document["unexpected_receipt_mutation"] = True
        value = json.dumps(document).encode()
    path.write_bytes(value)
    with pytest.raises(ValueError):
        load_stockout_export(root)


def test_missing_artifact_never_selects_a_fixture(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_stockout_export(tmp_path)
