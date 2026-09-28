"""Measure AI-00 source contracts without modifying source datasets or runtime."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from data.generator.common import BASE_DATE, deterministic_uuid
from data.generator.main import DatasetGenerationConfig, build_dataset
from data.generator.profile_engine import profile_defaults
from data.generator.quality import build_quality_report
from ml.evaluation.fixed_origin import build_daily_panel
from ml.evaluation.metrics import calculate_forecast_metrics
from ml.features.demand_forecast import build_demand_feature_rows
from ml.models.random_forest_forecast import build_training_features


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def load_tables(directory):
    tables = {}
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as source:
            tables[path.stem] = list(csv.DictReader(source))
    return tables


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def measure(first: Path, repeat: Path, contrast: Path):
    tables, other = load_tables(first), load_tables(contrast)
    manifest = json.loads((first / "dataset_manifest.json").read_text())
    assert manifest["profile"] == "small" and manifest["seed"] == 42
    defaults = profile_defaults("small")
    effective = {
        key: manifest["parameters"][key] or getattr(defaults, key)
        for key in ("days", "products", "stores", "warehouses")
    }
    effective.update(profile="small", seed=manifest["seed"], end_date=BASE_DATE.isoformat())
    counts = {name: len(rows) for name, rows in tables.items()}
    assert counts == manifest["row_counts"]
    assert counts["products"] == effective["products"] and counts["stores"] == effective["stores"]
    compared = {}
    for path in sorted(first.iterdir()):
        second = repeat / path.name
        entry = {
            "first_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "repeat_sha256": hashlib.sha256(second.read_bytes()).hexdigest(),
        }
        entry["bytes_equal"] = entry["first_sha256"] == entry["repeat_sha256"]
        if path.suffix == ".json":
            left, right = json.loads(path.read_text()), json.loads(second.read_text())
            left.pop("generated_at", None)
            right.pop("generated_at", None)
            entry["equal_excluding_generated_at"] = left == right
        compared[path.name] = entry
    config = DatasetGenerationConfig(profile="small", seed=42)
    features = build_demand_feature_rows(tables, config)
    contrast_features = build_demand_feature_rows(
        other, DatasetGenerationConfig(profile="small", products=20, seed=42)
    )
    sales, orders, items = tables["sales"], tables["orders"], tables["order_items"]
    products = {r["id"]: r for r in tables["products"]}
    order_by_ref = {r["order_reference"]: r for r in orders}
    order_by_id = {r["id"]: r for r in orders}
    sale_by_id = {r["id"]: r for r in sales}
    item_groups = defaultdict(list)
    for row in items:
        item_groups[row["order_id"]].append(row)
    item_sale = {}
    unmatched = []
    for order_id, group in item_groups.items():
        for index, item in enumerate(group):
            reference = order_by_id[order_id]["order_reference"]
            sku = products[item["product_id"]]["sku"]
            key = f"{reference}-{sku}-{index+1}"
            matched = sale_by_id.get(deterministic_uuid("sale", key))
            if matched:
                item_sale[item["id"]] = matched
            else:
                unmatched.append(item["id"])
    assert not unmatched, "Cannot reconstruct order-item/sale relationship from generator key"
    early = [
        r
        for r in sales
        if timestamp(r["sold_at"]) < timestamp(order_by_ref[r["order_reference"]]["ordered_at"])
    ]
    repeated_baskets = [
        key
        for key, rows in item_groups.items()
        if len({r["product_id"] for r in rows}) != len(rows)
    ]
    duplicate_lines = sum(
        len(rows) - len({r["product_id"] for r in rows}) for rows in item_groups.values()
    )
    order_total_mismatches = sum(
        sum(Decimal(r["total_amount"]) for r in item_groups[o["id"]]) != Decimal(o["order_total"])
        for o in orders
    )
    item_sale_mismatches = sum(
        any(
            i[k] != item_sale[i["id"]][k]
            for k in ("quantity", "unit_price", "total_amount", "currency", "product_id")
        )
        for i in items
    )
    returned_qty = Counter()
    for row in tables["returns"]:
        returned_qty[row["order_item_id"]] += int(row["quantity"])
    over_returned = sum(returned_qty[i["id"]] > int(i["quantity"]) for i in items)
    early_returns = [
        r
        for r in tables["returns"]
        if timestamp(r["returned_at"]) < timestamp(item_sale[r["order_item_id"]]["sold_at"])
    ]
    return_delays = [
        (
            timestamp(r["returned_at"]) - timestamp(item_sale[r["order_item_id"]]["sold_at"])
        ).total_seconds()
        / 86400
        for r in tables["returns"]
    ]
    price_groups, promo_groups = defaultdict(list), defaultdict(list)
    for r in tables["price_history"]:
        price_groups[r["product_id"]].append(r)
    for r in tables["promotions"]:
        promo_groups[r["product_id"]].append(r)
    price_stats = Counter()
    promo_stats = Counter()
    samples = {}
    for sale in sales:
        day = sale["sold_at"][:10]
        valid_prices = [
            p
            for p in price_groups[sale["product_id"]]
            if p["valid_from"] <= day and (not p["valid_to"] or day <= p["valid_to"])
        ]
        valid_promos = [
            p
            for p in promo_groups[sale["product_id"]]
            if p["starts_at"] <= day <= p["ends_at"]
            and p["channel"] in ("all", sale["channel"])
            and p["status"] == "active"
        ]
        if not valid_prices:
            price_stats["sales_without_price"] += 1
        elif len(valid_prices) > 1:
            price_stats["sales_with_overlapping_prices"] += 1
        else:
            price_stats["sales_with_one_price"] += 1
            if Decimal(sale["unit_price"]) != Decimal(valid_prices[0]["price"]):
                price_stats["realized_vs_calendar_price_mismatches"] += 1
            if valid_promos:
                expected = Decimal(valid_prices[0]["price"]) * (
                    1 - Decimal(valid_promos[0]["discount_percent"]) / 100
                )
                if Decimal(sale["unit_price"]) != expected.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ):
                    price_stats["realized_vs_discounted_calendar_mismatches"] += 1
        flagged = sale["promotion_applied"] == "true"
        if flagged:
            promo_stats["flagged_sales"] += 1
        if flagged and not valid_promos:
            promo_stats["flag_without_active_promotion"] += 1
        if valid_promos and not flagged:
            promo_stats["active_promotion_without_flag"] += 1
        if flagged != bool(valid_promos) and "promotion_mismatch" not in samples:
            samples["promotion_mismatch"] = {
                "sale_id": sale["id"],
                "day": day,
                "promotion_applied": sale["promotion_applied"],
                "declared_intervals": [
                    (p["starts_at"], p["ends_at"]) for p in promo_groups[sale["product_id"]]
                ],
            }
    date_start = BASE_DATE - timedelta(days=effective["days"] - 1)
    panel = build_daily_panel(
        features,
        tables["products"],
        tables["stores"],
        date_start=date_start,
        date_end=BASE_DATE,
        max_panel_rows=100_000,
        assume_synthetic_complete=True,
    )
    denominator = effective["days"] * len(products) * len(tables["stores"])
    assert len(panel) == denominator
    no_evidence = build_daily_panel(
        [],
        tables["products"][:1],
        tables["stores"][:1],
        date_start=BASE_DATE,
        date_end=BASE_DATE,
        max_panel_rows=1,
    )
    temporal = {}
    date_fields = {
        "sold_at",
        "ordered_at",
        "recorded_at",
        "occurred_at",
        "ingested_at",
        "generated_at",
        "created_at",
        "starts_at",
        "ends_at",
        "valid_from",
        "valid_to",
        "returned_at",
        "forecast_period_start",
        "forecast_period_end",
        "period_start",
        "period_end",
    }
    for name, rows in tables.items():
        temporal[name] = {}
        for field in sorted(set(rows[0]) & date_fields if rows else []):
            values = [r[field][:10] for r in rows if r.get(field)]
            temporal[name][field] = {
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "after_manifest_end": sum(v > manifest["date_end"] for v in values),
                "before_manifest_start": sum(v < manifest["date_start"] for v in values),
            }
    opening = Counter(
        (r["product_id"], r["warehouse_code"])
        for r in tables["stock_movements"]
        if r["movement_type"] == "initial_stock"
    )
    base_demo = build_dataset(DatasetGenerationConfig(profile="demo"))
    sale = dict(base_demo["sales"][0])
    base_demo["sales"] = [sale]
    before = build_demand_feature_rows(base_demo, DatasetGenerationConfig())[0]
    origin = date.fromisoformat(before["date"]) + timedelta(days=1)
    target = {**before, "date": origin.isoformat()}
    prior = build_training_features(target, [before], window_days=7, origin=origin)
    base_demo["sales"].append(
        {**sale, "id": "late-probe", "ingested_at": "2099-01-01T00:00:00+00:00"}
    )
    after = build_demand_feature_rows(base_demo, DatasetGenerationConfig())[0]
    later = build_training_features(target, [after], window_days=7, origin=origin)
    history = [
        {
            **before,
            "date": (origin - timedelta(days=n)).isoformat(),
            "observation_available_at": (origin - timedelta(days=n)).isoformat()
            + "T23:00:00+00:00",
            "units_sold": n,
        }
        for n in (2, 7, 8)
    ]
    gap = build_training_features(target, history, window_days=7, origin=origin)
    future = {
        **before,
        "date": origin.isoformat(),
        "units_sold": 99999,
        "observation_available_at": "2099-01-01T00:00:00+00:00",
    }
    unchanged = (
        build_training_features(target, [*history, future], window_days=7, origin=origin) == gap
    )
    tainted = {
        **target,
        "unit_price": 999999,
        "promotion_applied": "true",
        "inventory_on_hand": 999999,
        "stockout_flag": "true",
        "latent_demand": 999999,
    }
    unused_covariates = (
        build_training_features(tainted, history, window_days=7, origin=origin) == gap
    )
    mutated = deepcopy(tables)
    first_return = mutated["returns"][0]
    first_return["returned_at"] = "1900-01-01T00:00:00+00:00"
    chronology_gate = build_quality_report("small", mutated)["status"]
    mutated = deepcopy(tables)
    first_return = mutated["returns"][0]
    matching = next(i for i in mutated["order_items"] if i["id"] == first_return["order_item_id"])
    for index in (1, 2):
        mutated["returns"].append(
            {
                **first_return,
                "id": deterministic_uuid("return", f"audit-over-return-{index}"),
                "quantity": matching["quantity"],
            }
        )
    cumulative_gate = build_quality_report("small", mutated)["status"]
    zero = calculate_forecast_metrics(
        [{"actual_units": 0, "predicted_units": 100}], prediction_field="predicted_units"
    )
    empty = calculate_forecast_metrics([], prediction_field="predicted_units")
    return {
        "effective_config": effective,
        "manifest_parameters": manifest["parameters"],
        "row_counts": counts,
        "determinism": {
            "files": compared,
            "all_csv_identical": all(
                v["bytes_equal"] for k, v in compared.items() if k.endswith(".csv")
            ),
        },
        "identity": {
            "source_dataset_id_present": "dataset_id" in manifest,
            "byte_checksums_in_manifest": "checksums" in manifest,
            "feature_id_100": features[0]["dataset_id"],
            "feature_id_20": contrast_features[0]["dataset_id"],
            "feature_hash_100": digest(features),
            "feature_hash_20": digest(contrast_features),
            "feature_rows_100": len(features),
            "feature_rows_20": len(contrast_features),
        },
        "panel": {
            "valid_static_location_channel_pairs": len(tables["stores"]),
            "assumed_valid_daily_rows": denominator,
            "source_feature_rows": len(features),
            "source_feature_coverage": len(features) / denominator,
            "source_explicit_zero_rows": sum(int(r["quantity"]) == 0 for r in sales),
            "synthetic_ml_panel_rows": len(panel),
            "synthetic_ml_panel_statuses": dict(Counter(r["observation_status"] for r in panel)),
            "without_evidence_status": no_evidence[0]["observation_status"],
            "without_evidence_units": no_evidence[0]["units_sold"],
            "assumption": (
                "all active products x active stores; each store has one channel; "
                "all source days complete; no versioned assignments/lifecycle"
            ),
        },
        "dimensions": {
            "sku_with_whitespace": sum(
                any(c.isspace() for c in p["sku"]) for p in products.values()
            ),
            "category_brand_pairs": len({(p["category"], p["brand"]) for p in products.values()}),
            "categories": len({p["category"] for p in products.values()}),
            "brands": len({p["brand"] for p in products.values()}),
            "region_channel_pairs": sorted({(s["region"], s["channel"]) for s in tables["stores"]}),
        },
        "commerce": {
            "sales": len(sales),
            "orders": len(orders),
            "sales_before_order": len(early),
            "early_sale_example": {
                "sale_id": early[0]["id"],
                "sold_at": early[0]["sold_at"],
                "ordered_at": order_by_ref[early[0]["order_reference"]]["ordered_at"],
            }
            if early
            else None,
            "baskets_with_duplicate_product": len(repeated_baskets),
            "duplicate_product_lines": duplicate_lines,
            "order_total_mismatches": order_total_mismatches,
            "item_sale_mismatches": item_sale_mismatches,
            "returns": len(tables["returns"]),
            "returns_before_sale": len(early_returns),
            "cumulative_over_returns": over_returned,
            "return_delay_days_min_max": [min(return_delays), max(return_delays)],
        },
        "pricing": {
            **dict(price_stats),
            "sales": len(sales),
            "price_coverage": price_stats["sales_with_one_price"] / len(sales),
            "overlap_convention": "inclusive valid_from and valid_to",
        },
        "promotions": {
            **dict(promo_stats),
            **samples,
            "truth_day_offsets": {
                "post_promo_dip_25_28": [str(BASE_DATE - timedelta(days=d)) for d in (28, 25)],
                "promotion_10_24": [str(BASE_DATE - timedelta(days=d)) for d in (24, 10)],
                "pre_promo_softening_7_9": [str(BASE_DATE - timedelta(days=d)) for d in (9, 7)],
            },
        },
        "dates": {
            "manifest_start": manifest["date_start"],
            "manifest_end": manifest["date_end"],
            "tables": temporal,
            "watermarks_present": any("watermark" in k for k in manifest),
        },
        "inventory": {
            "snapshots": len(tables["inventory_snapshots"]),
            "opening_movements": sum(opening.values()),
            "product_stock_location_pairs": len(opening),
            "pairs_with_repeated_opening": sum(n > 1 for n in opening.values()),
            "extra_opening_movements": sum(n - 1 for n in opening.values()),
            "opening_counts_min_max": [min(opening.values()), max(opening.values())],
        },
        "ml_probes": {
            "calendar_gap": {
                k: gap[k]
                for k in (
                    "lag_1_units",
                    "lag_1_available",
                    "lag_7_units",
                    "lag_7_available",
                    "training_observation_count",
                )
            },
            "future_day_does_not_change_features": unchanged,
            "target_price_promo_stockout_inventory_truth_ignored": unused_covariates,
            "late_arrival_changes_old_origin": {
                k: [prior[k], later[k]] for k in prior if prior[k] != later[k]
            },
            "zero_metrics": zero,
            "empty_metrics": empty,
            "input_columns": sorted(gap),
        },
        "source_quality": {
            "original": json.loads((first / "quality_report.json").read_text())["summary"],
            "injected_return_before_sale_status": chronology_gate,
            "injected_cumulative_excess_return_status": cumulative_gate,
            "truth_in_sales_csv": sorted(
                set(sales[0])
                & {
                    "latent_demand",
                    "demand_noise",
                    "promotion_uplift",
                    "price_elasticity_effect",
                    "stockout_flag",
                    "data_quality_status",
                }
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--repeat", type=Path, required=True)
    parser.add_argument("--contrast", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.first, args.repeat, args.contrast)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"Source audit written to {args.output}")


if __name__ == "__main__":
    main()
