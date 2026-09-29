from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from data.generator.common import deterministic_uuid
from data.generator.configuration import DatasetGenerationConfig
from data.generator.dimension_schema import DIMENSION_COLUMNS
from data.generator.identity import canonical_json, json_sha256
from data.inventory.qualification import qualification_report, qualify_windows
from data.inventory.qualification_contract import MANIFEST, REPORT, WINDOWS, qualification_schema
from data.inventory.qualification_io import read_qualification, write_qualification
from data.inventory.run_source_dataset import build_source_dataset, default_inventory_config
from data.inventory.source_dataset_io import artifact, write_source_dataset
from data.inventory.ledger import InventoryLedger
from data.inventory.snapshots import snapshot_at
from data.inventory.source_tables import operational_from_tables
from data.inventory.stockout import diagnose_windows, stockout_episodes


def uid(label):
    return deterministic_uuid("qualification_test", label)


@pytest.fixture
def isolated():
    # Unit fixture for the eligibility layer, not a publishable/generated source.
    product, stock, other, selling = map(uid, ("product", "stock", "other", "selling"))
    known = "2026-06-30T00:00:00+00:00"
    origin = "2026-07-01T23:59:59.999999+00:00"
    finish = "2026-07-08T23:59:59.999999+00:00"
    end = "2026-07-09T00:00:00+00:00"
    tables = {n: [] for n in DIMENSION_COLUMNS}
    tables["product_catalog"] = [
        {
            "id": product,
            "launch_date": "2026-07-01",
            "discontinue_date": "",
            "status": "inactive",
            "available_at": known,
        }
    ]
    for channel in ("store", "online"):
        version = {
            "effective_from": "2026-07-01",
            "effective_to": "2026-07-09",
            "available_at": known,
            "selling_location_id": selling,
            "channel": channel,
        }
        tables["channel_assignments"].append(
            {
                **version,
                "id": uid("assignment" + channel),
                "legacy_store_id": uid("legacy" + channel),
            }
        )
        tables["assortment"].append(
            {**version, "id": uid("assortment" + channel), "product_id": product}
        )
        tables["fulfillment_routes"].append(
            {**version, "id": uid("route" + channel), "stock_location_id": stock}
        )
    tables["daily_demand_observations"] = []
    for offset in range(8):
        stamp = datetime(2026, 7, 1, tzinfo=UTC) + timedelta(days=offset)
        for channel in ("store", "online"):
            tables["business_calendar"].append(
                {
                    "business_date": stamp.date().isoformat(),
                    "selling_location_id": selling,
                    "channel": channel,
                    "location_open": "false",
                }
            )
            tables["daily_demand_observations"].append(
                {
                    "business_date": stamp.date().isoformat(),
                    "product_id": product,
                    "selling_location_id": selling,
                    "channel": channel,
                    "is_active_assortment": "true",
                    "source_data_complete": "true",
                    "quality_status": "valid",
                    "observation_status": "closed",
                    "location_open": "false",
                    "available_at": (stamp + timedelta(days=1)).isoformat(),
                    "observed_units": "0",
                }
            )
    tables["inventory_history_coverage"] = [
        {
            "coverage_id": uid("coverage"),
            "product_id": product,
            "stock_location_id": stock,
            "covered_from_at": "2026-07-01T00:00:00+00:00",
            "covered_through_at": end,
            "available_at": end,
        }
    ]
    diagnostic = {
        "product_id": product,
        "stock_location_id": stock,
        "origin": origin,
        "window_end_at": finish,
        "evaluated_at": end,
        "status": "evaluable",
        "reason": None,
        "incident_stockout": 0,
        "label_available_at": finish,
    }
    tables["inventory_window_diagnostics"] = [
        diagnostic,
        {**diagnostic, "stock_location_id": other},
    ]

    # The pure layer only uses opening; real IO supplies a fully validated TableContext.
    class Context:
        opening_at = "2026-07-01T00:00:00+00:00"

    return tables, Context(), diagnostic


def result(isolated):
    tables, context, diagnostic = isolated
    return next(
        r
        for r in qualify_windows(tables, context)
        if r["stock_location_id"] == diagnostic["stock_location_id"]
    )


def test_no_demand_closed_known_stock_is_negative_without_fake_positive(isolated):
    rows = qualify_windows(*isolated[:2])
    active = result(isolated)
    assert active["status"] == "evaluable" and active["incident_stockout"] == 0
    assert active["covered_sales_days"] == 7 and len(active["origin_route_ids"]) == 2
    assert len(rows) == 2  # shared channels do not duplicate physical positions
    unused = next(r for r in rows if r["stock_location_id"] != active["stock_location_id"])
    assert unused["reason"] == "inactive_assortment" and unused["incident_stockout"] is None
    report = qualification_report(rows, {"dataset_id": "test", "facts_ready": True})
    assert report["label_qualification"] == "not_evaluable"
    assert report["class_qualification_reason"] == "insufficient_classes"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("before_launch", "inactive_lifecycle"),
        ("discontinued_origin", "inactive_lifecycle"),
        ("discontinued_window", "window_inactive_lifecycle"),
        ("no_assortment", "inactive_assortment"),
        ("assortment_ends", "window_inactive_assortment"),
        ("route_missing", "route_missing"),
        ("route_gap", "window_route_missing"),
        ("late_route", "dimension_not_available"),
        ("late_catalog", "dimension_not_available"),
        ("late_future_route", "window_dimension_not_available"),
        ("calendar_missing", "window_calendar_missing"),
        ("coverage_missing", "inventory_coverage_incomplete"),
        ("coverage_wrong_stock", "inventory_coverage_incomplete"),
        ("coverage_short", "inventory_coverage_incomplete"),
        ("coverage_late", "outcomes_not_available"),
        ("panel_missing", "sales_coverage_incomplete"),
        ("panel_incomplete", "sales_coverage_incomplete"),
        ("panel_late", "outcomes_not_available"),
    ],
)
def test_unqualified_windows_never_get_zero_or_one(isolated, mutation, reason):
    tables, _, diagnostic = isolated
    catalog = tables["product_catalog"][0]
    if mutation == "before_launch":
        catalog["launch_date"] = "2026-07-02"
    elif mutation.startswith("discontinued"):
        catalog["discontinue_date"] = "2026-07-01" if mutation.endswith("origin") else "2026-07-05"
    elif mutation == "no_assortment":
        tables["assortment"] = []
    elif mutation == "assortment_ends":
        for row in tables["assortment"]:
            row["effective_to"] = "2026-07-05"
    elif mutation == "route_missing":
        tables["fulfillment_routes"] = []
    elif mutation == "route_gap":
        tables["fulfillment_routes"][0]["effective_to"] = "2026-07-05"
    elif mutation == "late_route":
        tables["fulfillment_routes"][0]["available_at"] = "2026-07-02T00:00:00+00:00"
    elif mutation == "late_catalog":
        catalog["available_at"] = "2026-07-02T00:00:00+00:00"
    elif mutation == "late_future_route":
        route = tables["fulfillment_routes"][0]
        route["effective_to"] = "2026-07-05"
        tables["fulfillment_routes"].append(
            {
                **route,
                "id": uid("future_route"),
                "effective_from": "2026-07-05",
                "effective_to": "2026-07-09",
                "available_at": "2026-07-06T00:00:00+00:00",
            }
        )
    elif mutation == "calendar_missing":
        tables["business_calendar"] = [
            r for r in tables["business_calendar"] if r["business_date"] != "2026-07-05"
        ]
    elif mutation == "coverage_missing":
        tables["inventory_history_coverage"] = []
    elif mutation == "coverage_wrong_stock":
        tables["inventory_history_coverage"][0]["stock_location_id"] = uid("other")
    elif mutation == "coverage_short":
        tables["inventory_history_coverage"][0]["covered_through_at"] = diagnostic["window_end_at"]
    elif mutation == "coverage_late":
        tables["inventory_history_coverage"][0]["available_at"] = "2026-07-10T00:00:00+00:00"
    elif mutation == "panel_missing":
        tables["daily_demand_observations"] = [
            r for r in tables["daily_demand_observations"] if r["business_date"] != "2026-07-05"
        ]
    elif mutation == "panel_incomplete":
        tables["daily_demand_observations"][-1]["source_data_complete"] = "false"
    elif mutation == "panel_late":
        tables["daily_demand_observations"][-1]["available_at"] = "2026-07-10T00:00:00+00:00"
    row = result(isolated)
    assert row["status"] == "not_evaluable" and row["reason"] == reason
    assert row["incident_stockout"] is None


@pytest.mark.parametrize(
    "status,reason",
    [
        ("already_stockout", None),
        ("not_evaluable", "inventory_unknown"),
        ("not_evaluable", "origin_state_unavailable"),
        ("not_evaluable", "incomplete_window"),
        ("not_evaluable", "outcomes_not_available"),
    ],
)
def test_physical_projection_exclusions_remain_null(isolated, status, reason):
    isolated[2].update(
        status=status, reason=reason, incident_stockout=None, label_available_at=None
    )
    row = result(isolated)
    assert (row["status"], row["reason"], row["incident_stockout"]) == (status, reason, None)


def test_inactive_zero_is_excluded_before_already_stockout(isolated):
    isolated[2].update(status="already_stockout", incident_stockout=None, label_available_at=None)
    isolated[0]["product_catalog"][0]["discontinue_date"] = "2026-07-01"
    assert result(isolated)["reason"] == "inactive_lifecycle"


def test_foreign_physical_coverage_and_full_sales_panel_do_not_qualify_position(isolated):
    isolated[0]["inventory_history_coverage"] = []
    assert result(isolated)["reason"] == "inventory_coverage_incomplete"


def test_route_switch_preserves_physical_eligibility_only_with_other_channels(isolated):
    route = isolated[0]["fulfillment_routes"][0]
    route["effective_to"] = "2026-07-05"
    isolated[0]["fulfillment_routes"].append(
        {
            **route,
            "id": uid("switch"),
            "stock_location_id": uid("other"),
            "effective_from": "2026-07-05",
            "effective_to": "2026-07-09",
        }
    )
    row = result(isolated)
    assert row["status"] == "evaluable" and len(row["window_route_ids"]) == 2
    # The old stock still has online demand, but never acquires the new route's lineage.
    assert uid("switch") not in row["window_route_ids"]


def test_class_coverage_requires_ready_source(isolated):
    rows = [result(isolated)]
    rows.append({**rows[0], "incident_stockout": 1})
    assert (
        qualification_report(rows, {"dataset_id": "test", "facts_ready": True})[
            "label_qualification"
        ]
        == "qualified"
    )
    report = qualification_report(rows, {"dataset_id": "test", "facts_ready": False})
    assert report["label_qualification"] == "not_evaluable"
    assert report["class_qualification_reason"] == "source_facts_not_ready"


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=10, products=4, stores=3, warehouses=2
    )
    config = default_inventory_config(generation)
    tables, context = build_source_dataset(generation, config)
    path = write_source_dataset(
        tables, context, generation, config, tmp_path_factory.mktemp("qualification-source")
    )
    return path, tables, context


def test_qualification_contract_schema_is_checked_in():
    assert (
        json.loads(Path("data/contracts/inventory_label_qualification.v1.schema.json").read_text())
        == qualification_schema()
    )


def test_verified_parent_roundtrip_repeat_and_no_source_mutation(source, tmp_path):
    parent, tables, context = source
    before = {str(p.relative_to(parent)): p.read_bytes() for p in parent.rglob("*") if p.is_file()}
    first = write_qualification(parent, tmp_path / "first")
    second = write_qualification(parent, tmp_path / "repeat")
    rows, report, manifest = read_qualification(first, parent)
    assert rows == qualify_windows(tables, context)
    assert first.name == second.name and first.name == manifest["qualification_id"]
    assert manifest["windows"] == json.loads((second / MANIFEST).read_text())["windows"]
    assert all(manifest[k] is False for k in ("source_ready", "inventory_ready", "model_ready"))
    assert report["data_class"] == "simulation_truth"
    assert write_qualification(parent, tmp_path / "first") == first
    assert before == {
        str(p.relative_to(parent)): p.read_bytes() for p in parent.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize(
    "fault",
    [
        "resealed_label",
        "resealed_report",
        "extra",
        "symlink",
        "placement",
        "ready",
        "duplicate_json",
    ],
)
def test_qualification_independently_rejects_tamper(source, tmp_path, fault):
    parent = source[0]
    path = write_qualification(parent, tmp_path)
    manifest_path = path / MANIFEST
    manifest = json.loads(manifest_path.read_text())
    if fault.startswith("resealed"):
        target = path / (WINDOWS if fault == "resealed_label" else REPORT)
        payload = json.loads(target.read_text())
        if fault == "resealed_label":
            payload[0]["incident_stockout"] = 0 if payload[0]["incident_stockout"] == 1 else 1
            manifest["descriptor"]["windows_sha256"] = json_sha256(payload)
            field = "windows"
        else:
            payload["positive_labels"] += 1
            manifest["descriptor"]["report_sha256"] = json_sha256(payload)
            field = "report"
        target.write_bytes(canonical_json(payload) + b"\n")
        manifest[field] = artifact(target, path)
        manifest["qualification_id"] = "inventory-labels-sha256-" + json_sha256(
            manifest["descriptor"]
        )
    elif fault == "extra":
        (path / "extra.json").write_text("{}")
    elif fault == "symlink":
        (path / "alias").symlink_to(path / REPORT)
    elif fault == "placement":
        manifest["windows"]["path"] = "facts/inventory_qualified_windows.json"
    elif fault == "ready":
        manifest["inventory_ready"] = True
    else:
        manifest_path.write_text('{"source_ready":false,' + manifest_path.read_text()[1:])
    if fault not in {"extra", "symlink", "duplicate_json"}:
        manifest_path.write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError):
        read_qualification(path, parent)


def test_corrupt_qualification_is_not_repaired(source, tmp_path):
    path = write_qualification(source[0], tmp_path)
    target = path / WINDOWS
    target.write_text("[]\n")
    with pytest.raises(ValueError):
        write_qualification(source[0], tmp_path)
    assert target.read_text() == "[]\n"


@pytest.mark.parametrize("mutation", ["future_after_window", "unavailable_at_origin"])
def test_future_or_unavailable_movement_cannot_rewrite_origin_or_fabricate_label(source, mutation):
    _, tables, context = source
    qualified = next(r for r in qualify_windows(tables, context) if r["status"] == "evaluable")
    origin = qualified["origin"]
    payload = operational_from_tables(tables, context)["ledger"]
    ledger = InventoryLedger.from_payload(payload)
    before = snapshot_at(ledger, snapshot_time=origin, as_of_time=origin)
    event = deepcopy(
        next(
            r
            for r in payload["movements"]
            if r["product_id"] == qualified["product_id"]
            and r["stock_location_id"] == qualified["stock_location_id"]
        )
    )
    happened = (
        datetime.fromisoformat(qualified["window_end_at"]) + timedelta(microseconds=1)
        if mutation == "future_after_window"
        else datetime.fromisoformat(origin) - timedelta(microseconds=1)
    )
    late = datetime.fromisoformat(context.projection.end_at) + timedelta(days=1)
    event.update(
        inventory_event_id=uid(mutation),
        quantity_delta=1,
        movement_type="inventory_adjustment",
        source_process="adjustment",
        source_reference="qualification negative test",
        occurred_at=happened.isoformat(),
        ingested_at=late.isoformat(),
        available_at=late.isoformat(),
        sequence=max(r["sequence"] for r in payload["movements"]) + 1,
        order_id=None,
        supplier_id=None,
        transfer_id=None,
    )
    payload["movements"].append(event)
    changed = InventoryLedger.from_payload(payload)
    assert before == snapshot_at(changed, snapshot_time=origin, as_of_time=origin)
    episodes, _ = stockout_episodes(changed, context.projection, [])
    diagnostics = diagnose_windows(
        changed, context.projection, episodes, origin=origin, evaluated_at=context.evaluated_at
    )
    target = next(
        r
        for r in diagnostics
        if r["product_id"] == qualified["product_id"]
        and r["stock_location_id"] == qualified["stock_location_id"]
    )
    projection_view = {**tables, "inventory_window_diagnostics": [target]}
    row = qualify_windows(projection_view, context)[0]
    if mutation == "future_after_window":
        assert row == qualified
    else:
        assert row["reason"] == "origin_state_unavailable" and row["incident_stockout"] is None
