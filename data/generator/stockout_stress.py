"""Prospective latent-demand shock recipe; never an operational input feature.

The factor participates in the existing multiplicative demand formula and the
full chronological commerce/inventory simulation. It does not edit labels or
observed sales after generation. The versioned profile and generator fingerprint
bind this recipe into genuine source identities.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from data.generator.configuration import ResolvedGenerationConfig

PROFILE = "ai-stockout-stress-v1"
POLICY_VERSION = "stockout-prospective-demand-shock-1.0.0"
SHOCK_START_DAY = 49
SHOCK_DAYS = 7
SHOCK_FACTOR = Decimal(2)
PRODUCT_MODULUS = 3


def selected_product(product_id: str) -> bool:
    """Stable membership decided from identity, independent of targets/scores."""
    return (
        int.from_bytes(hashlib.sha256(product_id.encode()).digest(), "big") % PRODUCT_MODULUS == 0
    )


def anomaly_factor(
    config: ResolvedGenerationConfig, product_id: str, business_date: date
) -> Decimal:
    index = (business_date - config.start_date).days
    if (
        config.profile == PROFILE
        and SHOCK_START_DAY <= index < SHOCK_START_DAY + SHOCK_DAYS
        and selected_product(product_id)
    ):
        return SHOCK_FACTOR
    return Decimal(1)
