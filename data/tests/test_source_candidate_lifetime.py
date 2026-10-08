"""Native builders release original commerce containers before projection."""

import weakref

import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies import source_cohort as planned
from data.generator.configuration import DatasetGenerationConfig
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory import source_cohort_batch_v2 as ordinary
from data.inventory.source_dataset_contract import PRIVATE_TABLES, SOURCE_TABLES


@pytest.mark.parametrize("kind", ["ordinary", "demand", "physical"])
def test_original_request_containers_expire_but_private_tables_survive(kind, monkeypatch):
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2,
        seed=42, forecast_plan_days=14,
    )
    module = ordinary if kind == "ordinary" else planned
    build = module.build_dataset
    project = module.project_inventory
    refs = {}
    requests = ("orders", "order_items", "sales")
    observations = []

    class OwnedRows(list):
        pass

    def observe_build(*args, **kwargs):
        candidate = build(*args, **kwargs)
        for name in (*requests, *PRIVATE_TABLES):
            assert candidate[name]
            candidate[name] = OwnedRows(candidate[name])
            refs[name] = weakref.ref(candidate[name])
        return candidate

    def observe_projection(*args, **kwargs):
        observations.append({name: ref() is None for name, ref in refs.items()})
        assert all(refs[name]() is None for name in requests)
        assert all(refs[name]() is not None for name in PRIVATE_TABLES)
        return project(*args, **kwargs)

    monkeypatch.setattr(module, "build_dataset", observe_build)
    monkeypatch.setattr(module, "project_inventory", observe_projection)
    config = default_inventory_config(generation)
    if kind == "ordinary":
        tables, _ = ordinary.build_source_dataset_fast(generation, config)
    else:
        payload = (example_plan if kind == "demand" else physical_example_plan)(generation)
        tables, _ = planned.build_tables(generation, payload, config)
    assert len(observations) == 1
    assert set(tables) == set(SOURCE_TABLES)
    assert all(tables[name] is refs[name]() for name in PRIVATE_TABLES)
