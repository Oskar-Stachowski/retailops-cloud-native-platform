"""Validate the generated AI v2 schema, plus relationships JSON Schema cannot express."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from app.services.realtime_consumer import InvalidRealtimeEventError

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contracts" / "intelligence-v2"
TOPIC = "retailops.intelligence.v2"
EVENT_NAMESPACE = UUID("b85cb398-e62a-5f70-91ed-6c0fbe868a50")
MAX_EVENT_BYTES = 32768


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@lru_cache
def event_validator(event_type: str = "forecast_generated") -> Draft202012Validator:
    if event_type not in {"forecast_generated", "anomaly_detected", "stockout_risk_scored"}:
        msg = "intelligence_event_type_unsupported"
        raise ValueError(msg)
    schema = json.loads((CONTRACT_DIR / (event_type + ".schema.json")).read_bytes())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_event(event: dict[str, Any], *, transport_topic: str | None = None) -> None:
    try:
        if transport_topic != TOPIC or len(canonical_bytes(event)) > MAX_EVENT_BYTES:
            raise ValueError
        if event.get("event_type") == "recommendation_generated":
            if os.getenv("RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT") != "1":
                raise ValueError
            # Loaded only for this event to keep canonical hashing independent of adapters.
            from app.services.intelligence_suggestion_contract import (  # noqa: PLC0415
                validate_suggestion,
            )

            validate_suggestion(event)
        else:
            event_type = event.get("event_type", "")
            if next(event_validator(event_type).iter_errors(event), None) is not None:
                raise ValueError
            if event_type == "forecast_generated":
                _forecast_relationships(event)
            else:
                from app.services import intelligence_model_contract  # noqa: PLC0415

                intelligence_model_contract.model_relationships(event)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        msg = "intelligence_v2_contract_invalid"
        raise InvalidRealtimeEventError(msg) from exc


def _forecast_relationships(event: dict[str, Any]) -> None:
    payload = event["payload"]
    origin = datetime.fromisoformat(payload["forecast_origin"])
    generated = datetime.fromisoformat(payload["generated_at"])
    occurred = datetime.fromisoformat(event["occurred_at"])
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
    key["forecast_origin"] = origin.isoformat().replace("+00:00", "Z")
    prediction_id = "prediction-sha256-" + content_hash(
        {
            "projection": "forecast-v12-read-v1",
            "artifact_id": payload["prediction_dataset_id"],
            "key": key,
        }
    )
    if (
        origin.time().isoformat() != "23:59:59"
        or date.fromisoformat(payload["target_date"])
        != origin.date() + timedelta(days=payload["horizon_days"])
        or generated < origin
        or occurred != generated
        or datetime.fromisoformat(event["ingested_at"]) != occurred
        or datetime.fromisoformat(payload["freshness"]["evaluated_at"]) != generated
        or generated >= datetime.fromisoformat(payload["approval_valid_until"])
        or payload["prediction_id"] != prediction_id
        or event["event_id"] != str(uuid5(EVENT_NAMESPACE, "forecast_generated:" + prediction_id))
        or event["correlation_id"] != payload["inference_run_id"]
    ):
        msg = "forecast_binding"
        raise ValueError(msg)
    prediction = payload["prediction"]
    candidate, baseline = prediction["candidate"], prediction["baseline"]
    if (
        candidate["median"] != baseline["median"]
        or candidate["interval"] != baseline["interval"]
        or prediction["metadata"]["selected"] != prediction["metadata"]["baseline"]
        or (
            prediction.get("exclusion_reason") is not None
            and any(
                value is not None
                for functional in (candidate, baseline)
                for value in functional.values()
            )
        )
    ):
        msg = "forecast_reference"
        raise ValueError(msg)
    for functional in (candidate, baseline):
        interval = functional["interval"]
        if interval is not None and (
            interval["lower"] > interval["upper"]
            or (
                functional["median"] is not None
                and not interval["lower"] <= functional["median"] <= interval["upper"]
            )
        ):
            msg = "forecast_interval"
            raise ValueError(msg)
    _freshness_relationships(payload["freshness"])


def _freshness_relationships(freshness: dict[str, Any]) -> None:
    expected = (
        "current"
        if freshness["reason"] == "within_policy"
        else (
            "unknown"
            if freshness["reason"]
            in {
                "source_watermark_unavailable",
                "source_watermark_policy_unsupported",
                "source_watermark_not_ready",
                "source_observation_unavailable",
            }
            else "stale"
        )
    )
    measures = (
        freshness["source_watermark_age_seconds"],
        freshness["source_watermark_origin_lag_seconds"],
    )
    if (
        freshness["status"] != expected
        or (
            any(v is not None for v in measures)
            if freshness["source_watermark"] is None
            else any(v is None for v in measures)
        )
        or (
            freshness["source_watermark_as_of"] is not None
            and datetime.fromisoformat(freshness["source_watermark_as_of"])
            > datetime.fromisoformat(freshness["evaluated_at"])
        )
        or (
            freshness["status"] == "current"
            and (
                freshness["source_watermark"] is None
                or freshness["source_completeness_status"] != "complete"
                or freshness["source_watermark_origin_lag_seconds"] != 0
                or freshness["observation_lag_days"] is None
                or freshness["observation_lag_days"] > freshness["max_observation_lag_days"]
                or freshness["origin_age_seconds"] > freshness["max_origin_age_seconds"]
            )
        )
    ):
        msg = "forecast_freshness"
        raise ValueError(msg)
