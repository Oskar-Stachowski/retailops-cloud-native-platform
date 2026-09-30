from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from shutil import copytree

import pytest

from data.anomalies.candidate_io import MANIFEST, PATHS, read_candidate, write_candidate
from data.anomalies.contract import AnomalyPlan, plan_schema
from data.anomalies.example import example_plan
from data.anomalies.scenarios import build_scenario, evaluate_effects
from data.generator.configuration import DatasetGenerationConfig, resolve_generation_config
from data.generator.demand_quality import validate_demand
from data.generator.identity import canonical_json, json_sha256
from data.generator.main import build_dataset
from data.inventory.source_dataset_io import artifact
from data.inventory.source_contract import SourceInventoryConfig
from data.inventory.run_source_dataset import default_inventory_config
from data.generator.source_quality import project_facts
from ml.features.fact_input import HISTORY_FACT_COLUMNS, validate_fact_input


@pytest.fixture(scope="module")
def generation():
    return DatasetGenerationConfig(profile="ai-smoke", days=30, products=8, stores=3, warehouses=2)


@pytest.fixture(scope="module")
def plan(generation):
    return example_plan(generation)


@pytest.fixture(scope="module")
def sample(generation, plan):
    return build_scenario(generation, plan)


@pytest.fixture(scope="module")
def paired(generation, plan):
    return build_dataset(generation), build_dataset(
        generation, anomaly_plan=AnomalyPlan.from_payload(plan)
    )


def test_schema_is_executable_and_checked_in(plan):
    from jsonschema import Draft202012Validator

    path = Path("data/contracts/business_anomaly_plan.v1.schema.json")
    assert json.loads(path.read_text()) == plan_schema()
    Draft202012Validator.check_schema(plan_schema())
    Draft202012Validator(plan_schema()).validate(plan)


@pytest.mark.parametrize(
    "fault",
    [
        "unknown_type",
        "label_only",
        "overlap",
        "control_overlap",
        "wrong_seed",
        "one_day_duration",
        "multi_day_duration",
        "drop_duration",
        "spike_magnitude",
        "drop_magnitude",
        "negative_magnitude",
        "unknown_field",
        "invalid_date",
        "duplicate_id",
        "no_clean_control",
        "wrong_grain_control",
        "oversized_window",
        "unsupported_shape",
        "unsupported_version",
    ],
)
def test_plan_rejects_ambiguous_or_inapplicable_process_contract(plan, fault):
    value = deepcopy(plan)
    one = next(r for r in value["injections"] if r["injection_type"] == "one_day_spike")
    multi = next(r for r in value["injections"] if r["injection_type"] == "multi_day_spike")
    drop = next(r for r in value["injections"] if r["injection_type"] == "sustained_drop")
    clean = next(r for r in value["controls"] if r["control_type"] == "clean")
    if fault == "unknown_type":
        one["injection_type"] = "return_spike"
    elif fault == "label_only":
        one["affected_fields"] = []
    elif fault == "overlap":
        multi["start_date"] = one["start_date"]
    elif fault == "control_overlap":
        clean["end_date"] = one["start_date"]
    elif fault == "wrong_seed":
        one["seed"] += 1
    elif fault == "one_day_duration":
        one["end_date"] = multi["start_date"]
    elif fault == "multi_day_duration":
        multi["end_date"] = multi["start_date"]
    elif fault == "drop_duration":
        drop["end_date"] = drop["start_date"]
    elif fault == "spike_magnitude":
        one["magnitude"] = "1"
    elif fault == "drop_magnitude":
        drop["magnitude"] = "1"
    elif fault == "negative_magnitude":
        drop["magnitude"] = "-1"
    elif fault == "unknown_field":
        value["model_label"] = "oracle"
    elif fault == "invalid_date":
        one["start_date"] = "2026-02-30"
    elif fault == "duplicate_id":
        clean["id"] = one["id"]
    elif fault == "no_clean_control":
        value["controls"] = [c for c in value["controls"] if c["control_type"] != "clean"]
    elif fault == "wrong_grain_control":
        clean["product_id"] = "00000000-0000-4000-8000-000000000001"
    elif fault == "oversized_window":
        drop.update(start_date="2020-01-01", end_date="2023-01-01")
    elif fault == "unsupported_shape":
        one["shape"] = "label_only"
    else:
        value["contract_version"] = "business-anomaly-plan-2.0.0"
    with pytest.raises((ValueError, TypeError)):
        AnomalyPlan.from_payload(value)


@pytest.mark.parametrize(
    "fault", ["unknown_product", "out_of_range", "wrong_generator_seed", "closed_day"]
)
def test_scope_is_resolved_against_actual_lifecycle_and_calendar(generation, plan, paired, fault):
    normal, _ = paired
    value = deepcopy(plan)
    if fault == "unknown_product":
        for row in [*value["injections"], *value["controls"]]:
            row["product_id"] = "00000000-0000-4000-8000-000000000001"
    elif fault == "out_of_range":
        for row in [*value["injections"], *value["controls"]]:
            row["start_date"] = row["start_date"].replace("2026", "2025")
            row["end_date"] = row["end_date"].replace("2026", "2025")
    elif fault == "wrong_generator_seed":
        value["seed"] += 1
        for row in value["injections"]:
            row["seed"] = value["seed"]
    else:
        normal = deepcopy(normal)
        target = value["injections"][0]
        for row in normal["business_calendar"]:
            if (
                row["business_date"] == target["start_date"]
                and row["selling_location_id"] == target["selling_location_id"]
                and row["channel"] == target["channel"]
            ):
                row["location_open"] = "false"
    with pytest.raises(ValueError):
        AnomalyPlan.from_payload(value).factors(normal, resolve_generation_config(generation))


def test_process_changes_units_before_baskets_and_preserves_other_factors(generation, plan, paired):
    normal, injected = paired
    parsed = AnomalyPlan.from_payload(plan)
    assert evaluate_effects(normal, injected, parsed)["status"] == "passed"
    assert (
        validate_demand(injected, resolve_generation_config(generation), anomaly_plan=parsed)[
            "status"
        ]
        == "passed"
    )
    assert normal["daily_demand_truth"] != injected["daily_demand_truth"]
    assert normal["sales"] != injected["sales"]
    with pytest.raises(ValueError, match="Demand hard gate"):
        validate_demand(injected, resolve_generation_config(generation))


def test_same_seed_repeat_and_permutation_are_identical(generation, plan, paired):
    normal, injected = paired
    changed = deepcopy(plan)
    changed["injections"].reverse()
    changed["controls"].reverse()
    assert (
        AnomalyPlan.from_payload(changed).model_dump()
        == AnomalyPlan.from_payload(plan).model_dump()
    )
    assert build_dataset(generation, anomaly_plan=AnomalyPlan.from_payload(changed)) == injected
    assert build_dataset(generation) == normal


def test_label_change_without_process_change_fails(generation, plan, paired):
    normal, injected = paired
    altered = deepcopy(plan)
    altered["injections"][0]["magnitude"] = (
        "0.1" if altered["injections"][0]["injection_type"] == "sustained_drop" else "4"
    )
    parsed = AnomalyPlan.from_payload(altered)
    with pytest.raises(ValueError):
        evaluate_effects(normal, injected, parsed)
    with pytest.raises(ValueError):
        validate_demand(injected, resolve_generation_config(generation), anomaly_plan=parsed)


def test_stock_is_shared_and_each_injection_has_real_inventory_effect_accounting(sample):
    assert {e["injection_type"] for e in sample["effects"]["episodes"]} == {
        "one_day_spike",
        "multi_day_spike",
        "sustained_drop",
    }
    assert (
        sample["reconciliation"]["latent_quantity"]
        == sample["reconciliation"]["observed_quantity"]
        + sample["reconciliation"]["lost_sales_quantity"]
    )
    for episode in sample["effects"]["episodes"]:
        normal, injected = (
            episode["normal_inventory_outcome"],
            episode["injected_inventory_outcome"],
        )
        assert normal["latent_quantity"] != injected["latent_quantity"]
        assert (
            injected["latent_quantity"]
            == injected["observed_quantity"] + injected["lost_sales_quantity"]
        )
    assert any(
        e["injected_inventory_outcome"]["lost_sales_quantity"] > 0
        for e in sample["effects"]["episodes"]
    )
    assert sample["source_ready"] is sample["model_ready"] is sample["anomaly_ready"] is False


def test_uncensored_spikes_and_drop_change_actual_sales(generation, plan):
    payload = default_inventory_config(generation).model_dump()
    payload["stock"]["opening_quantity"] = 10000
    source = build_scenario(generation, plan, SourceInventoryConfig.from_payload(payload))
    for episode in source["effects"]["episodes"]:
        normal, injected = (
            episode["normal_inventory_outcome"],
            episode["injected_inventory_outcome"],
        )
        assert normal["lost_sales_quantity"] == injected["lost_sales_quantity"] == 0
        if episode["injection_type"] == "sustained_drop":
            assert injected["observed_quantity"] < normal["observed_quantity"]
        else:
            assert injected["observed_quantity"] > normal["observed_quantity"]


def test_neutral_controls_are_real_and_unchanged(sample):
    assert {c["control_type"] for c in sample["effects"]["controls"]} == {
        "clean",
        "promotion",
        "seasonality",
        "insufficient_history",
    }
    assert all(c["unchanged_daily_grains"] > 0 for c in sample["effects"]["controls"])
    assert all(
        c["inventory_outcome_unchanged"]
        for c in sample["effects"]["controls"]
        if c["control_type"] == "clean"
    )


@pytest.mark.parametrize("kind", ["promotion", "seasonality", "insufficient_history"])
def test_mislabelled_neutral_control_is_rejected(plan, paired, kind):
    normal, injected = deepcopy(paired)
    parsed = AnomalyPlan.from_payload(plan)
    control = next(c for c in parsed.controls if c.control_type == kind)
    if kind == "insufficient_history":
        parsed = parsed.model_copy(update={"minimum_history_observations": 1})
        # Move the claimed cold-start window later while retaining a neutral process.
        clean = next(c for c in parsed.controls if c.control_type == "clean")
        changed = control.model_copy(
            update={"start_date": clean.start_date, "end_date": clean.start_date}
        )
        parsed = parsed.model_copy(update={"controls": [changed]})
    else:
        for candidate in (normal, injected):
            for row in candidate["daily_demand_truth"]:
                key = tuple(
                    row[f]
                    for f in ("business_date", "product_id", "selling_location_id", "channel")
                )
                if key in control.daily_keys():
                    for field in (
                        ("promotion_factor",)
                        if kind == "promotion"
                        else ("weekly_factor", "seasonal_factor")
                    ):
                        row[field] = "1"
    with pytest.raises(ValueError):
        evaluate_effects(normal, injected, parsed)


def test_truth_is_separate_from_source_facts_and_feature_allowlist(sample):
    forbidden = {
        "injection_type",
        "magnitude",
        "seed",
        "anomaly_factor",
        "latent_units",
        "baseline_latent_units",
    }
    for rows in sample["commerce"].values():
        for row in rows:
            assert not forbidden.intersection(row)
    projection = project_facts(sample["commerce"])
    assert set(projection["tables"]) == set(HISTORY_FACT_COLUMNS)
    assert all(
        not forbidden.intersection(row) for rows in projection["tables"].values() for row in rows
    )
    projection["tables"]["anomaly_injections"] = sample["effects"]["episodes"]
    with pytest.raises(ValueError, match="allowlist"):
        validate_fact_input(projection)


def test_bundle_roundtrip_repeat_and_immutability(sample, tmp_path):
    first = write_candidate(sample, tmp_path / "first")
    second = write_candidate(sample, tmp_path / "second")
    a, b = read_candidate(first), read_candidate(second)
    assert a["candidate_id"] == b["candidate_id"]
    assert a["descriptor"] == b["descriptor"]
    assert set(a["artifacts"]) == set(PATHS)
    assert write_candidate(sample, tmp_path / "first") == first
    target = first / PATHS[0]
    target.write_text(target.read_text() + "broken")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        write_candidate(sample, tmp_path / "first")
    assert target.read_bytes() == before


def test_resealed_label_only_tamper_fails_independent_process_replay(sample, tmp_path):
    directory = write_candidate(sample, tmp_path)
    path = directory / PATHS[2]
    injections = json.loads(path.read_text())
    injections["episodes"][0]["injected_latent_units"] += 1
    path.write_bytes(canonical_json(injections) + b"\n")
    manifest = json.loads((directory / MANIFEST).read_text())
    manifest["artifacts"][PATHS[2]] = artifact(path, directory)
    manifest["descriptor"]["artifacts"] = manifest["artifacts"]
    manifest["candidate_id"] = "anomaly-candidate-sha256-" + json_sha256(manifest["descriptor"])
    (directory / MANIFEST).write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError, match="process replay"):
        read_candidate(directory)


@pytest.fixture(scope="module")
def published(sample, tmp_path_factory):
    return write_candidate(sample, tmp_path_factory.mktemp("ai07-published"))


@pytest.mark.parametrize(
    "fault",
    ["extra_file", "symlink", "truth_placement", "ready_claim", "version", "duplicate_json"],
)
def test_candidate_reader_rejects_unsafe_or_unqualified_layout(published, tmp_path, fault):
    directory = tmp_path / "candidate"
    copytree(published, directory)
    manifest_path = directory / MANIFEST
    manifest = json.loads(manifest_path.read_text())
    if fault == "extra_file":
        (directory / "extra.json").write_text("{}")
    elif fault == "symlink":
        (directory / "alias").symlink_to(directory / PATHS[0])
    elif fault == "truth_placement":
        manifest["artifacts"][PATHS[2]]["path"] = "facts/anomaly_injections.json"
        manifest["descriptor"]["artifacts"] = manifest["artifacts"]
        manifest["candidate_id"] = "anomaly-candidate-sha256-" + json_sha256(manifest["descriptor"])
    elif fault == "ready_claim":
        manifest["anomaly_ready"] = True
    elif fault == "version":
        manifest["schema_version"] = "anomaly-scenario-candidate-2.0.0"
    else:
        manifest_path.write_text(
            '{"schema_version":"anomaly-scenario-candidate-1.0.0",' + manifest_path.read_text()[1:]
        )
    if fault in {"truth_placement", "ready_claim", "version"}:
        manifest_path.write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises((ValueError, TypeError)):
        read_candidate(directory)


def test_generation_is_bounded_and_legacy_does_not_accept_injections(plan):
    with pytest.raises(ValueError, match="5000"):
        build_scenario(DatasetGenerationConfig(profile="ai-dev"), plan)
    with pytest.raises(ValueError, match="AI profile"):
        build_dataset(
            DatasetGenerationConfig(profile="demo"), anomaly_plan=AnomalyPlan.from_payload(plan)
        )
