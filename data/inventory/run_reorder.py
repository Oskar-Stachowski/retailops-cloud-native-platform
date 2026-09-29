from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.inventory.contract import require
from data.inventory.ledger import InventoryLedger
from data.inventory.reorder import ReorderReview, review_reorder
from data.inventory.reorder_contract import ReorderConfig, parse_history_coverage
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.supplier_fulfillment import FulfillmentConfig, simulate_fulfillment
from data.inventory.supplier_truth import validate_supplier_truth

if TYPE_CHECKING:
    from data.inventory.replenishment_contract import ReplenishmentReceipt

NOT_READY = {"config_unavailable", "inventory_unknown", "history_missing", "supplier_missing"}


def _simulate_and_reconcile(
    supply: dict,
    inventory: dict,
    review: ReorderReview,
    settings: FulfillmentConfig,
    truth: dict,
) -> dict:
    book = ReplenishmentBook.from_payload(supply)
    parameters = {
        r.supplier_id: r
        for r in validate_supplier_truth(truth, {s.supplier_id for s in book.suppliers})
    }
    sequence = max(m["sequence"] for m in inventory["movements"]) + 1
    samples = []
    receipts: list[ReplenishmentReceipt] = []
    for order in review.orders:
        sample = simulate_fulfillment(
            order, parameters[order.supplier_id], settings, first_sequence=sequence
        )
        sequence += len(sample.receipts)
        receipts.extend(sample.receipts)
        samples.append(
            {
                "order_id": order.replenishment_order_id,
                "simulation_id": sample.simulation_id,
                "disrupted": sample.disrupted,
                "lead_days": sample.lead_days,
            }
        )
    combined = {
        **supply,
        "replenishment_orders": [
            *supply["replenishment_orders"],
            *(o.model_dump() for o in review.orders),
        ],
        "delivery_plan_versions": [
            *supply["delivery_plan_versions"],
            *(p.model_dump() for p in review.plans),
        ],
        "replenishment_receipts": [
            *supply["replenishment_receipts"],
            *(r.model_dump() for r in receipts),
        ],
    }
    complete = ReplenishmentBook.from_payload(combined)
    receipt_ids = {r.receipt_id for r in receipts}
    movements = [
        m.record() for m in complete.receipt_movements() if m.source_reference in receipt_ids
    ]
    augmented_ledger = InventoryLedger.from_payload(
        {**inventory, "movements": [*inventory["movements"], *movements]}
    )
    reconciliation = complete.reconcile_ledger(augmented_ledger)
    if review.decisions:
        origin = review.decisions[0].origin
        initial = InventoryLedger.from_payload(inventory).balances_at(origin, known_at=origin)
        require(
            initial == augmented_ledger.balances_at(origin, known_at=origin),
            "Scheduled deliveries leaked into ordering inventory.",
        )
    return {
        "data_class": "simulation_truth",
        "effective_config": settings.model_dump(),
        "supplier_parameters": [
            r.model_dump() for r in sorted(parameters.values(), key=lambda r: r.supplier_id)
        ],
        "samples": samples,
        "scheduled_receipts": [r.model_dump() for r in receipts],
        "receipt_movements": movements,
        "reconciliation": reconciliation,
        "reconciled_movements_sha256": json_sha256(
            [m.record() for m in augmented_ledger.movements]
        ),
    }


def run(
    supply_path: Path,
    ledger_path: Path,
    config_path: Path,
    coverage_path: Path,
    fulfillment_path: Path,
    truth_path: Path,
    origin: str,
) -> dict:
    paths = {
        "supply": supply_path,
        "ledger": ledger_path,
        "policy": config_path,
        "history_coverage": coverage_path,
        "fulfillment": fulfillment_path,
        "supplier_truth": truth_path,
    }
    inputs = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    ledger = InventoryLedger.from_payload(inputs["ledger"])
    book = ReplenishmentBook.from_payload(inputs["supply"])
    config = ReorderConfig.from_payload(inputs["policy"])
    coverage = parse_history_coverage(inputs["history_coverage"])
    settings = FulfillmentConfig.from_payload(inputs["fulfillment"])
    review = review_reorder(ledger, book, config, coverage, origin)
    simulation = _simulate_and_reconcile(
        inputs["supply"], inputs["ledger"], review, settings, inputs["supplier_truth"]
    )
    operational = {"effective_config": config.model_dump(), **review.record()}
    files = tuple(
        str(p.relative_to(Path(__file__).resolve().parents[2]))
        for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    contracts = tuple(
        "data/contracts/" + name + ".v1.schema.json"
        for name in (
            "inventory_ledger",
            "replenishment",
            "supplier_simulation_truth",
            "reorder_config",
            "inventory_history_coverage",
            "supplier_fulfillment_config",
        )
    )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "status": "not_ready" if any(d.status in NOT_READY for d in review.decisions) else "passed",
        "scope": "AI 06.3 standalone reorder and supplier fulfillment; not chronological source acceptance",
        "inventory_ready": False,
        "requested_configuration": {
            "operational_policy": inputs["policy"],
            "simulation_truth": inputs["fulfillment"],
        },
        "input_sha256": {name: file_sha256(path) for name, path in paths.items()},
        "operational": operational,
        "operational_sha256": json_sha256(operational),
        "simulation_truth": simulation,
        "simulation_sha256": json_sha256(simulation),
        "positions_at_origin": ledger.balances_at(origin, known_at=origin),
        "code_provenance": code_provenance(code_fingerprint((*files, *contracts))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded AI 06.3 reorder/fulfillment fixture."
    )
    for option in (
        "supply",
        "ledger",
        "config",
        "coverage",
        "fulfillment-config",
        "supplier-truth",
        "output",
    ):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.supply,
            args.ledger,
            args.config,
            args.coverage,
            args.fulfillment_config,
            args.supplier_truth,
            args.origin,
        )
    except (ValueError, OSError, OverflowError) as error:
        result = {
            "status": "failed",
            "scope": "AI 06.3 reorder/fulfillment contract",
            "error": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
