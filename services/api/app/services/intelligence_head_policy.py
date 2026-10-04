"""Explicit private operator selections; reader grants never approve a model."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, Self

from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator

from app.auth.intelligence import PrivateContract, ReleaseID, Sha256, Symbol
from app.services.intelligence_contract import content_hash

PredictionID = Annotated[str, Field(pattern=r"^prediction-sha256-[0-9a-f]{64}$")]
OutputID = Annotated[str, Field(pattern=r"^v12-forecasts-sha256-[0-9a-f]{64}$")]
RunID = Annotated[str, Field(pattern=r"^run-[0-9a-f]{32}$")]
MAX_HEAD_ROWS = 2800
MAX_POLICY_BYTES = 1024 * 1024
MAX_REVIEW_AGE = timedelta(minutes=15)


class HeadRow(PrivateContract):
    prediction_id: PredictionID
    payload_sha256: Sha256


class OwnerReviewReceipt(PrivateContract):
    """Exact pinned AI lifecycle review response, delivered by the trusted operator."""

    model_name: Literal["retailops-demand-forecast-v12"]
    model_version: Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
    approval_id: Annotated[str, Field(pattern=r"^v12-inference-release-sha256-[0-9a-f]{64}$")]
    approval_sha256: Sha256
    rejected: Literal[False]
    release_id: ReleaseID
    aliases: dict[str, Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]] = Field(
        min_length=1, max_length=3
    )
    pending_decisions: tuple[str, ...] = Field(max_length=0)
    runtime_status: Literal["not_integrated"]

    @field_validator("rejected", mode="before")
    @classmethod
    def false_only(cls, value: object) -> bool:
        if value is not False:
            msg = "head_rejected_model"
            raise ValueError(msg)
        return False

    @field_validator("aliases")
    @classmethod
    def controlled_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) - {"candidate", "champion", "rollback"}:
            msg = "head_uncontrolled_alias"
            raise ValueError(msg)
        return value


class ApprovedForecastHead(PrivateContract):
    """Operator attestation of a previously verified publication, not a new ML approval."""

    selection_sha256: Sha256
    reviewed_by: Symbol
    owner_review_receipt_sha256: Sha256
    owner_review_receipt: OwnerReviewReceipt
    reviewed_at: datetime
    valid_until: datetime
    release_id: ReleaseID
    inference_run_id: RunID
    prediction_dataset_id: OutputID
    forecast_origin: datetime
    generated_at: datetime
    model_name: Literal["retailops-demand-forecast-v12"]
    model_version: Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
    approval_sha256: Sha256
    approval_valid_until: datetime
    runtime_pin_sha256: Sha256
    image_digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    receipt_id: Annotated[str, Field(pattern=r"^v12-computation-sha256-[0-9a-f]{64}$")]
    source_dataset_id: Annotated[str, Field(pattern=r"^source-sha256-[0-9a-f]{64}$")]
    curated_dataset_id: Annotated[str, Field(pattern=r"^curated-sha256-[0-9a-f]{64}$")]
    feature_set_id: Annotated[str, Field(pattern=r"^features-sha256-[0-9a-f]{64}$")]
    profile_id: Annotated[str, Field(pattern=r"^batch-profile-sha256-[0-9a-f]{64}$")]
    product_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=20)
    selling_location_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=5)
    channel: Literal["store", "online"]
    horizon_days: Literal[7, 14]
    rows: tuple[HeadRow, ...] = Field(min_length=1, max_length=1400)

    @field_validator(
        "reviewed_at", "valid_until", "forecast_origin", "generated_at", "approval_valid_until"
    )
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            msg = "head_time_requires_utc"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def complete_selection(self) -> Self:
        ids = [row.prediction_id for row in self.rows]
        if (
            self.forecast_origin.time().isoformat() != "23:59:59"
            or not self.forecast_origin <= self.generated_at <= self.reviewed_at
            or not self.reviewed_at < self.valid_until <= self.reviewed_at + MAX_REVIEW_AGE
            or self.valid_until > self.approval_valid_until
            or ids != sorted(set(ids))
            or len(set(self.product_ids)) != len(self.product_ids)
            or len(set(self.selling_location_ids)) != len(self.selling_location_ids)
            or len(ids)
            != len(self.product_ids) * len(self.selling_location_ids) * self.horizon_days
            or self.owner_review_receipt_sha256
            != content_hash(self.owner_review_receipt.model_dump(mode="json"))
            or self.owner_review_receipt.release_id != self.release_id
            or self.owner_review_receipt.model_name != self.model_name
            or self.owner_review_receipt.model_version != self.model_version
            or self.owner_review_receipt.approval_sha256 != self.approval_sha256
            or self.owner_review_receipt.aliases.get("champion") != self.model_version
            or self.selection_sha256
            != content_hash(self.model_dump(mode="json", exclude={"selection_sha256"}))
        ):
            msg = "head_selection_identity_or_coverage"
            raise ValueError(msg)
        return self


class ForecastHeadPolicy(PrivateContract):
    version: Literal["retailops-forecast-head-policy-1.0"]
    policy_sha256: Sha256
    heads: tuple[ApprovedForecastHead, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def independent_selections(self) -> Self:
        series = [
            (product, location, head.channel)
            for head in self.heads
            for product in head.product_ids
            for location in head.selling_location_ids
        ]
        ids = [row.prediction_id for head in self.heads for row in head.rows]
        artifacts = [head.prediction_dataset_id for head in self.heads]
        if (
            len(series) != len(set(series))
            or len(artifacts) != len(set(artifacts))
            or len(ids) != len(set(ids))
            or len(ids) > MAX_HEAD_ROWS
            or self.policy_sha256
            != content_hash(self.model_dump(mode="json", exclude={"policy_sha256"}))
        ):
            msg = "head_policy_identity_or_overlap"
            raise ValueError(msg)
        return self


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document = dict(pairs)
    if len(document) != len(pairs):
        msg = "head_duplicate_json_field"
        raise ValueError(msg)
    return document


def private_document(path: Path, *, max_bytes: int) -> bytes:
    """Bounded regular owner-only file; nonblocking open also rejects FIFOs safely."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            msg = "head_private_file_required"
            raise ValueError(msg)
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        msg = "head_private_file_budget"
        raise ValueError(msg)
    json.loads(raw, object_pairs_hook=_unique_object)
    return raw


def head_policy() -> ForecastHeadPolicy:
    """Reload every request: replacing or clearing the private policy revokes immediately."""
    configured = os.getenv("RETAILOPS_INTELLIGENCE_HEAD_POLICY")
    if not configured:
        raise HTTPException(503, detail="intelligence_head_policy_unavailable")
    try:
        return ForecastHeadPolicy.model_validate_json(
            private_document(Path(configured), max_bytes=MAX_POLICY_BYTES)
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="intelligence_head_policy_unavailable") from exc
