"""Explicit source 2.8 contract for process-level anomaly scenarios."""

from __future__ import annotations

from typing import Literal

from data.inventory.source_dataset_contract import (
    SHA256,
    Artifact,
    SourceDescriptor,
    SourceManifest,
)

VERSION = "2.8.0"
POLICY = "anomaly-source-acceptance-1.0.0"
SCENARIO_PATH = "simulation_truth/anomaly_scenario.json"


class AnomalySourceDescriptor(SourceDescriptor):
    identity_version: Literal["anomaly-source-identity-1.0.0"]  # type: ignore[assignment]  # explicit wire version override
    schema_version: Literal["2.8.0"]  # type: ignore[assignment]  # explicit wire version override
    generator_version: Literal["1.0.0"]  # type: ignore[assignment]  # explicit wire version override
    source_policy_version: Literal["anomaly-source-acceptance-1.0.0"]  # type: ignore[assignment]  # explicit wire version override
    scenario_plan_sha256: SHA256
    scenario_schema_sha256: SHA256


class AnomalySourceManifest(SourceManifest):
    schema_version: Literal["2.8.0"]  # type: ignore[assignment]  # explicit wire version override
    descriptor: AnomalySourceDescriptor
    scenario: Artifact


def source_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **AnomalySourceManifest.model_json_schema(),
    }
