from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from data.generator.identity import code_fingerprint, code_provenance, file_sha256, json_sha256
from data.inventory.contract import LEDGER_VERSION, LEGACY_ADAPTER_VERSION
from data.inventory.ledger import InventoryLedger
from data.inventory.legacy import legacy_stock_movements


def verify(input_path: Path, occurred_through: str, known_at: str | None = None) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    ledger = InventoryLedger.from_payload(payload)
    balances = ledger.balances_at(occurred_through, known_at=known_at)
    legacy = legacy_stock_movements(ledger)
    files = tuple(
        str(path.relative_to(Path(__file__).resolve().parents[2]))
        for path in sorted(Path(__file__).resolve().parent.glob("*.py"))
    )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "scope": "AI 06.1 standalone inventory contract; not generator/source acceptance",
        "contract_version": LEDGER_VERSION,
        "legacy_adapter_version": LEGACY_ADAPTER_VERSION,
        "inventory_ready": False,
        "input_sha256": file_sha256(input_path),
        "ordered_movements_sha256": json_sha256([m.record() for m in ledger.movements]),
        "legacy_projection_sha256": json_sha256(legacy),
        "opening_policy": payload["opening_policy"],
        "reservation_policy": payload["reservation_policy"],
        "occurred_through": occurred_through,
        "known_at": known_at,
        "movement_count": len(ledger.movements),
        "opening_count": sum(m.movement_type == "opening_stock" for m in ledger.movements),
        "positions": balances,
        "transit": ledger.transit_at(occurred_through, known_at=known_at),
        "code_provenance": code_provenance(
            code_fingerprint((*files, "data/contracts/inventory_ledger.v1.schema.json"))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and replay the AI 06.1 ledger contract.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--occurred-through", required=True)
    parser.add_argument("--known-at")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.input, args.occurred_through, args.known_at)
    except (ValueError, OSError) as error:
        result = {"status": "failed", "scope": "AI 06.1 inventory contract", "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "report": str(args.output)}))  # noqa: T201 - CLI receipt
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
