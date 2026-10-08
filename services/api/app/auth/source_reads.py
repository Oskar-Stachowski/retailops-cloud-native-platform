"""Private service grants for bounded source reads, separate from ML credentials."""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID  # noqa: TC003 - Pydantic resolves these annotations at runtime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field

from app.auth.intelligence import PrivateContract, Sha256, Symbol
from app.domain.models import Channel  # noqa: TC001 - Pydantic resolves the grant schema

Resource = Literal["products", "sales", "inventory-snapshots", "forecasts", "inventory-risks"]
bearer = HTTPBearer(auto_error=False, scheme_name="SourceReadCredential")


class SourcePrincipal(PrivateContract):
    principal_id: Symbol
    credential_sha256: Sha256
    resources: tuple[Resource, ...] = Field(min_length=1, max_length=5)
    product_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    channels: tuple[Channel, ...] = Field(max_length=4)
    warehouse_codes: tuple[Symbol, ...] = Field(max_length=5)


class SourceAccessPolicy(PrivateContract):
    version: Literal["retailops-source-access-1.0"]
    principals: tuple[SourcePrincipal, ...] = Field(min_length=1, max_length=32)


@lru_cache
def access_policy() -> SourceAccessPolicy | None:
    value = os.getenv("RETAILOPS_SOURCE_ACCESS_POLICY")
    if not value:
        return None
    try:
        descriptor = os.open(Path(value), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                raise ValueError
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError
        policy = SourceAccessPolicy.model_validate_json(raw)
        identities = [p.principal_id for p in policy.principals]
        credentials = [p.credential_sha256 for p in policy.principals]
        if len(set(identities)) != len(identities) or len(set(credentials)) != len(credentials):
            raise ValueError
        return policy
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="source_access_policy_unavailable") from exc


def verified_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> SourcePrincipal:
    if credentials is None or not 32 <= len(credentials.credentials) <= 256:
        raise HTTPException(
            401, detail="source_credentials_required", headers={"WWW-Authenticate": "Bearer"}
        )
    policy = access_policy()
    digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    if policy is not None:
        for principal in policy.principals:
            if hmac.compare_digest(digest, principal.credential_sha256):
                return principal
    raise HTTPException(
        401, detail="source_credentials_invalid", headers={"WWW-Authenticate": "Bearer"}
    )


def authorize(principal: SourcePrincipal, resource: Resource, product_id: UUID) -> None:
    if resource not in principal.resources or product_id not in principal.product_ids:
        raise HTTPException(403, detail="source_scope_denied")
