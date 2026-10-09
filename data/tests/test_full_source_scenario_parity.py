"""Full native candidate bytes must match the independently recorded old revision.

Only fingerprints of previously exposed tiny native controls are stored. They
cover every candidate field, not just selected effects or the new implementation
compared against itself. Changes require a scientific compatibility review.
"""

import json
from pathlib import Path

import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import build_physical_scenario, physical_example_plan
from data.anomalies.scenarios import build_scenario
from data.generator.configuration import DatasetGenerationConfig
from data.generator.identity import json_sha256


REFERENCE = json.loads((Path(__file__).parent / "fixtures/ai09-paired-scenario-parity-v1.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: f"{case['family']}-{case['seed']}")
def test_every_native_candidate_field_matches_accepted_reference(case):
    assert REFERENCE["accepted_reference_commit"] == "ff2504a9cf6e4f46040c8327901b7bcb82d115c0"
    generation = DatasetGenerationConfig(**REFERENCE["configuration"], seed=case["seed"])
    plan_builder, builder = (
        (example_plan, build_scenario) if case["family"] == "demand"
        else (physical_example_plan, build_physical_scenario)
    )
    plan = plan_builder(generation)
    assert json_sha256(plan) == case["plan_sha256"]
    result = builder(generation, plan)
    assert json_sha256(result["effects"]) == case["effects_sha256"]
    assert json_sha256(result) == case["full_candidate_sha256"]
