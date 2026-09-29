"""Generator-only scheduling; outputs are not knowledge available at ordering."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from math import ceil
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field, ValidationError

from data.generator.common import deterministic_uuid
from data.generator.identity import json_sha256
from data.inventory.contract import require, utc_timestamp
from data.inventory.replenishment_contract import (
    Positive,
    ReplenishmentOrder,
    ReplenishmentReceipt,
    SupplyRecord,
)

# Pydantic resolves the decimal annotation at runtime.
from data.inventory.supplier_truth import NonnegativeDecimal  # noqa: TC001

if TYPE_CHECKING:
    from data.inventory.supplier_truth import SupplierTruth

FULFILLMENT_VERSION = "supplier-fulfillment-two-point-1.0.0"


class FulfillmentConfig(SupplyRecord):
    contract_version: Literal["supplier-fulfillment-config-1.0.0"]
    data_class: Literal["simulation_truth"]
    process_version: Literal["supplier-fulfillment-two-point-1.0.0"]
    seed: Annotated[int, Field(ge=0)]
    lead_time_distribution: Literal["two_point_mean_plus_minus_std"]
    minimum_lead_days: Positive
    maximum_lead_days: Positive
    disruption_delay_days: Positive
    partial_fraction: NonnegativeDecimal
    partial_receipt_gap_days: Positive
    ingestion_delay_seconds: Annotated[int, Field(ge=0)]
    availability_delay_seconds: Annotated[int, Field(ge=0)]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> FulfillmentConfig:
        try:
            parsed = cls.model_validate(payload)
        except ValidationError as error:
            msg = "Invalid supplier fulfillment configuration."
            raise ValueError(msg) from error
        require(parsed.minimum_lead_days <= parsed.maximum_lead_days, "Invalid lead-time bounds.")
        require(
            0 < Decimal(parsed.partial_fraction) < 1,
            "Partial fraction must be between zero and one.",
        )
        return parsed


def fulfillment_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **FulfillmentConfig.model_json_schema(),
    }


@dataclass(frozen=True)
class FulfillmentResult:
    simulation_id: str
    disrupted: bool
    lead_days: int
    receipts: tuple[ReplenishmentReceipt, ...]


def _draw(seed: int, order_id: str, purpose: str) -> int:
    value = f"{FULFILLMENT_VERSION}:{seed}:{order_id}:{purpose}".encode()
    return int.from_bytes(hashlib.sha256(value).digest(), "big")


def simulate_fulfillment(
    order: ReplenishmentOrder,
    truth: SupplierTruth,
    config: FulfillmentConfig,
    *,
    first_sequence: int,
) -> FulfillmentResult:
    config = FulfillmentConfig.from_payload(config.model_dump())
    require(type(first_sequence) is int and first_sequence >= 0, "Invalid receipt sequence.")
    require(order.supplier_id == truth.supplier_id, "Supplier truth does not match order.")
    reliability = Fraction(Decimal(truth.reliability))
    require(0 <= reliability <= 1, "Invalid supplier reliability.")
    ordered = utc_timestamp(order.ordered_at)
    ingested, available = utc_timestamp(order.ingested_at), utc_timestamp(order.available_at)
    require(ordered <= ingested <= available, "Invalid order availability chronology.")
    sign = 1 if _draw(config.seed, order.replenishment_order_id, "lead-sign") % 2 else -1
    base = Fraction(Decimal(truth.lead_time_mean_days)) + sign * Fraction(
        Decimal(truth.lead_time_std_days)
    )
    lead = min(config.maximum_lead_days, max(config.minimum_lead_days, ceil(base)))
    disrupted = _draw(
        config.seed, order.replenishment_order_id, "disruption"
    ) * reliability.denominator >= reliability.numerator * (1 << 256)
    if disrupted:
        lead += config.disruption_delay_days
    quantity = order.ordered_quantity
    quantities: tuple[int, ...]
    if disrupted and quantity > 1:
        fraction = Fraction(Decimal(config.partial_fraction))
        partial = max(1, quantity * fraction.numerator // fraction.denominator)
        quantities = (partial, quantity - partial)
    else:
        quantities = (quantity,)
    identity = json_sha256(
        {
            "order": order.model_dump(),
            "supplier_truth": truth.model_dump(),
            "configuration": config.model_dump(),
        }
    )
    receipts = []
    for part, actual_quantity in enumerate(quantities):
        received = ordered + timedelta(days=lead + part * config.partial_receipt_gap_days)
        received_ingestion = max(
            ingested, received + timedelta(seconds=config.ingestion_delay_seconds)
        )
        received_availability = max(
            available, received_ingestion + timedelta(seconds=config.availability_delay_seconds)
        )
        receipts.append(
            ReplenishmentReceipt(
                receipt_id=deterministic_uuid("replenishment_receipt", f"{identity}:{part}"),
                replenishment_order_id=order.replenishment_order_id,
                product_id=order.product_id,
                supplier_id=order.supplier_id,
                stock_location_id=order.stock_location_id,
                received_quantity=actual_quantity,
                unit_of_measure=order.unit_of_measure,
                received_at=received.isoformat(),
                ingested_at=received_ingestion.isoformat(),
                available_at=received_availability.isoformat(),
                sequence=first_sequence + part,
                source_reference=f"supplier-simulation:{FULFILLMENT_VERSION}:{identity}:{part}",
            )
        )
    return FulfillmentResult(identity, disrupted, lead, tuple(receipts))
