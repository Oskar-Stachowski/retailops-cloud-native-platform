from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.inventory.ledger import InventoryLedger
from data.inventory.replenishment import ReplenishmentBook
from data.inventory.replenishment_contract import REPLENISHMENT_VERSION


def verify(input_path: Path, ledger_path: Path, known_at: str) -> dict:
    book = ReplenishmentBook.from_payload(json.loads(input_path.read_text(encoding="utf-8")))
    ledger = InventoryLedger.from_payload(json.loads(ledger_path.read_text(encoding="utf-8")))
    reconciliation = book.reconcile_ledger(ledger)
    orders = book.orders_at(known_at)
    files = tuple(
        str(path.relative_to(Path(__file__).resolve().parents[2]))
        for path in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "scope": "AI 06.2 standalone supply/ledger reconciliation; not generator/source acceptance",
        "contract_version": REPLENISHMENT_VERSION,
        "inventory_ready": False,
        "input_sha256": file_sha256(input_path),
        "ledger_sha256": file_sha256(ledger_path),
        "receipt_movements_sha256": json_sha256([m.record() for m in book.receipt_movements()]),
        "known_orders_sha256": json_sha256(orders),
        "known_at": known_at,
        "supplier_count": len(book.suppliers),
        "quote_count": len(book.product_suppliers),
        "reconciliation": reconciliation,
        "known_orders": orders,
        "positions": ledger.balances_at(known_at, known_at=known_at),
        "code_provenance": code_provenance(
            code_fingerprint(
                (
                    *files,
                    "data/contracts/inventory_ledger.v1.schema.json",
                    "data/contracts/replenishment.v1.schema.json",
                    "data/contracts/supplier_simulation_truth.v1.schema.json",
                )
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate AI 06.2 supply against actual ledger receipts."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--known-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.input, args.ledger, args.known_at)
    except (ValueError, OSError) as error:
        result = {
            "status": "failed",
            "scope": "AI 06.2 supply/ledger contract",
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
