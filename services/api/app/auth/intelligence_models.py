"""Private personal model grants distinguish sales scopes from physical stock scopes."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Literal, Self

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, model_validator

from app.auth.intelligence import PrivateContract, Sha256, Symbol, read_private_policy

AnomalyRelease = Annotated[str, Field(pattern=r"^anomaly-release-sha256-[0-9a-f]{64}$")]
StockoutRelease = Annotated[str, Field(pattern=r"^stockout-release-sha256-[0-9a-f]{64}$")]
bearer = HTTPBearer(auto_error=False, scheme_name="ModelIntelligenceCredential")


class AnomalyScope(PrivateContract):
    product_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=20)
    selling_location_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=5)
    channels: tuple[Literal["store", "online", "marketplace", "wholesale"], ...] = Field(
        min_length=1, max_length=4
    )
    currencies: tuple[Literal["PLN", "EUR"], ...] = Field(min_length=1, max_length=2)
    release_ids: tuple[AnomalyRelease, ...] = Field(min_length=1, max_length=32)


class StockoutScope(PrivateContract):
    product_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=20)
    stock_location_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=5)
    release_ids: tuple[StockoutRelease, ...] = Field(min_length=1, max_length=32)


class ModelPrincipal(PrivateContract):
    principal_id: Symbol
    credential_sha256: Sha256
    capabilities: tuple[Literal["anomaly:read", "stockout:read"], ...] = Field(
        min_length=1, max_length=2
    )
    anomaly_scope: AnomalyScope | None = None
    stockout_scope: StockoutScope | None = None

    @model_validator(mode="after")
    def scopes(self) -> Self:
        if (
            len(self.capabilities) != len(set(self.capabilities))
            or ("anomaly:read" in self.capabilities) != (self.anomaly_scope is not None)
            or ("stockout:read" in self.capabilities) != (self.stockout_scope is not None)
        ):
            msg = "model_intelligence_grant_scope"
            raise ValueError(msg)
        return self


class ModelAccessPolicy(PrivateContract):
    version: Literal["retailops-model-intelligence-access-1.0"]
    principals: tuple[ModelPrincipal, ...] = Field(min_length=1, max_length=32)


def model_access_policy() -> ModelAccessPolicy | None:
    raw = read_private_policy("RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY")
    if raw is None:
        return None
    try:
        policy = ModelAccessPolicy.model_validate_json(raw)
        ids = [item.principal_id for item in policy.principals]
        digests = [item.credential_sha256 for item in policy.principals]
        if len(ids) != len(set(ids)) or len(digests) != len(set(digests)):
            msg = "model_intelligence_duplicate_principal"
            raise ValueError(msg)
        return policy
    except ValueError as exc:
        raise HTTPException(503, detail="intelligence_access_policy_unavailable") from exc


def verified_model_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> ModelPrincipal:
    if credentials is not None and 32 <= len(credentials.credentials) <= 256:
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        policy = model_access_policy()
        if policy is not None:
            for principal in policy.principals:
                if hmac.compare_digest(digest, principal.credential_sha256):
                    return principal
    raise HTTPException(
        401,
        detail="model_intelligence_credentials_required",
        headers={"WWW-Authenticate": "Bearer"},
    )
