"""Rebuild source 2.8 and reconcile every source table against its private plan."""

from __future__ import annotations

from typing import TYPE_CHECKING

from data.anomalies.candidate_io import candidate_plan_schema, parse_candidate_plan
from data.anomalies.contract import AnomalyPlan
from data.anomalies.physical_contract import PhysicalAnomalyPlan
from data.anomalies.physical_scenarios import build_physical_scenario
from data.anomalies.scenarios import build_scenario
from data.anomalies.source_contract import POLICY, VERSION
from data.generator.identity import json_sha256
from data.inventory.contract import require
from data.inventory.run_source_dataset import build_source_dataset
from data.inventory.source_dataset_contract import table_schema_document
from data.inventory.source_dataset_io import normalize_source

if TYPE_CHECKING:
    from data.generator.configuration import DatasetGenerationConfig
    from data.inventory.source_contract import SourceInventoryConfig
    from data.inventory.source_tables import TableContext


def table_contract() -> dict:
    return {**table_schema_document(), "source_version": VERSION}


def extend_descriptor(desc: dict, plan: dict) -> dict:
    return {
        **desc,
        "identity_version": "anomaly-source-identity-1.0.0",
        "schema_version": VERSION,
        "generator_version": "1.0.0",
        "source_policy_version": POLICY,
        "table_schema_sha256": json_sha256(table_contract()),
        "scenario_plan_sha256": json_sha256(parse_candidate_plan(plan).model_dump()),
        "scenario_schema_sha256": json_sha256(candidate_plan_schema(plan)),
    }


def build_tables(
    generation: DatasetGenerationConfig,
    payload: dict,
    config: SourceInventoryConfig,
    *,
    evaluated_at: str | None = None,
) -> tuple[dict, TableContext]:
    plan = parse_candidate_plan(payload)
    return build_source_dataset(
        generation,
        config,
        evaluated_at=evaluated_at,
        anomaly_plan=plan if isinstance(plan, AnomalyPlan) else None,
        physical_plan=plan if isinstance(plan, PhysicalAnomalyPlan) else None,
    )


def scenario_document(
    tables: dict,
    context: TableContext,
    generation: DatasetGenerationConfig,
    config: SourceInventoryConfig,
    payload: dict,
) -> dict:
    plan = parse_candidate_plan(payload)
    candidate = (build_scenario if isinstance(plan, AnomalyPlan) else build_physical_scenario)(
        generation, plan.model_dump(), config
    )
    expected, expected_context = build_tables(
        generation, plan.model_dump(), config, evaluated_at=context.evaluated_at
    )
    require(
        normalize_source(expected) == tables and expected_context == context,
        "Anomaly source disagrees with independent process replay.",
    )
    return {
        "data_class": "simulation_truth",
        "plan": plan.model_dump(),
        "effects": candidate["effects"],
    }
