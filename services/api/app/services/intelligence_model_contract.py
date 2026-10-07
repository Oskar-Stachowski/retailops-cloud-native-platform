"""Native anomaly/risk identities and status semantics, independent of the AI runtime."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import uuid5

from app.services.intelligence_contract import (
    CONTRACT_DIR,
    EVENT_NAMESPACE,
    content_hash,
    event_validator,
)

MODEL_TYPES = {"anomaly_detected", "stockout_risk_scored"}


def utc(value: str) -> str:
    return datetime.fromisoformat(value).isoformat().replace("+00:00", "Z")


@lru_cache
def decision_fields() -> tuple[str, ...]:
    registry = json.loads((CONTRACT_DIR / "registry.json").read_bytes())
    return tuple(registry["native_identity_fields"]["anomaly_detected"])


def model_relationships(event: dict[str, Any]) -> None:
    kind, item = event["event_type"], event["payload"]
    if kind not in MODEL_TYPES:
        msg = "intelligence_model_type"
        raise ValueError(msg)
    generated = utc(item["generated_at"])
    if (
        utc(event["occurred_at"]) != generated
        or utc(event["ingested_at"]) != generated
        or event["correlation_id"] != item["inference_run_id"]
        or datetime.fromisoformat(item["generated_at"]) < datetime.fromisoformat(item["as_of"])
    ):
        msg = "intelligence_model_time_or_run_binding"
        raise ValueError(msg)
    if kind == "anomaly_detected":
        _anomaly(item)
        decision = {name: item[name] for name in decision_fields()}
        decision["scoring_origin"] = utc(decision["scoring_origin"])
        identity = "anomaly-sha256-" + content_hash(
            {"batch_id": item["batch_id"], "decision": decision}
        )
        result_id = item["anomaly_id"]
    else:
        _risk(item)
        lineage = dict(item["lineage"])
        if lineage["source_watermark"] is not None:
            lineage["source_watermark"] = utc(lineage["source_watermark"])
        identity = "risk-sha256-" + content_hash(
            {
                "product_id": item["product_id"],
                "stock_location_id": item["stock_location_id"],
                "as_of": utc(item["as_of"]),
                "run_id": item["inference_run_id"],
                "release_id": item["release_id"],
                "source": lineage,
            }
        )
        result_id = item["risk_id"]
    if identity != result_id or event["event_id"] != str(
        uuid5(EVENT_NAMESPACE, kind + ":" + identity)
    ):
        msg = "intelligence_model_result_identity"
        raise ValueError(msg)


def _anomaly(item: dict[str, Any]) -> None:
    origin = datetime.fromisoformat(item["scoring_origin"])
    if (
        item["role"] != "batch"
        or origin.date().isoformat() <= item["business_date"]
        or origin > datetime.fromisoformat(item["as_of"])
        or item["observed_window"] != {"start": item["business_date"], "end": item["business_date"]}
        or utc(item["detected_at"]) != utc(item["generated_at"])
        or item["inference_run_id"] != item["batch_id"]
        or (item["alert"] is True) != (item["signal_episode_id"] is not None)
        or item["inventory_context"]["on_hand"] != item["on_hand"]
        or item["promotion_context"]["offered"] != item["promotion_offered"]
        or item["inventory_context"]["status"]
        != (
            "unavailable"
            if item["on_hand"] is None
            else "potential_stockout"
            if item["on_hand"] == 0
            else "no_stockout_signal"
        )
        or item["alert_status"]
        != (
            "insufficient_data"
            if item["status"] == "insufficient_data"
            else "open"
            if item["alert"]
            else "no_alert"
        )
    ):
        msg = "intelligence_anomaly_context"
        raise ValueError(msg)
    if item["status"] == "scored":
        if (
            item["input_status"] != "ready_input"
            or any(
                item[name] is None
                for name in (
                    "score",
                    "threshold",
                    "alert",
                    "severity",
                    "observed_units",
                    "expected_units",
                )
            )
            or item["alert"] != (item["score"] > item["threshold"])
            or (item["severity"] == "none") != (item["alert"] is False)
            or item["residual_units"] != item["observed_units"] - item["expected_units"]
        ):
            msg = "intelligence_anomaly_decision"
            raise ValueError(msg)
    elif any(item[name] is not None for name in ("score", "threshold", "alert", "severity")):
        msg = "intelligence_anomaly_insufficient_input"
        raise ValueError(msg)


def _risk(item: dict[str, Any]) -> None:
    scored = item["status"] == "scored"
    if (
        (item["probability"] is not None) != scored
        or (item["status_reason"] is None) != scored
        or (item["risk_band"] is not None) != scored
        or (
            item["status"] in {"scored", "already_stockout"}
            and item["inventory_freshness_status"] != "current"
        )
        or (item["status"] == "stale_input" and item["inventory_freshness_status"] != "stale")
        or item["model_name"].endswith("test-mechanics")
        != (item["quality_status"] == "mechanics_only")
    ):
        msg = "intelligence_risk_status"
        raise ValueError(msg)


def validate_model_payload(kind: str, item: dict[str, Any]) -> None:
    identity = item["anomaly_id"] if kind == "anomaly_detected" else item["risk_id"]
    event = {
        "event_id": str(uuid5(EVENT_NAMESPACE, kind + ":" + identity)),
        "event_type": kind,
        "schema_version": "2.0",
        "topic": "retailops.intelligence.v2",
        "source": "retailops-ai",
        "correlation_id": item["inference_run_id"],
        "occurred_at": item["generated_at"],
        "ingested_at": item["generated_at"],
        "payload": item,
    }
    event_validator(kind).validate(event)
    model_relationships(event)


def model_partition_key(event: dict[str, Any]) -> str:
    kind, item = event["event_type"], event["payload"]
    key = {"event_type": kind, "product_id": item["product_id"]}
    if kind == "anomaly_detected":
        key.update(
            observation_type=item["event_type"],
            selling_location_id=item["selling_location_id"],
            channel=item["channel"],
            currency=item["currency"],
        )
    elif kind == "stockout_risk_scored":
        key["stock_location_id"] = item["stock_location_id"]
    else:
        msg = "intelligence_model_type"
        raise ValueError(msg)
    return content_hash(key)
