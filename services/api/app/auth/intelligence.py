"""Private, explicitly scoped opaque credentials for AI reads; no demo-user fallback."""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

Symbol = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ReleaseID = Annotated[str, Field(pattern=r"^v12-model-release-sha256-[0-9a-f]{64}$")]
bearer = HTTPBearer(auto_error=False, scheme_name="IntelligenceCredential")


class PrivateContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class IntelligencePrincipal(PrivateContract):
    principal_id: Symbol
    credential_sha256: Sha256
    capabilities: tuple[Literal["forecast:read"], ...] = Field(min_length=1, max_length=1)
    product_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=20)
    selling_location_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=5)
    channels: tuple[Literal["store", "online"], ...] = Field(min_length=1, max_length=2)
    release_ids: tuple[ReleaseID, ...] = Field(min_length=1, max_length=32)


class IntelligenceAccessPolicy(PrivateContract):
    version: Literal["retailops-intelligence-access-1.0"]
    principals: tuple[IntelligencePrincipal, ...] = Field(min_length=1, max_length=32)


@lru_cache
def access_policy() -> IntelligenceAccessPolicy | None:
    path = os.getenv("RETAILOPS_INTELLIGENCE_ACCESS_POLICY")
    if not path:
        return None
    try:
        descriptor = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW)
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
        policy = IntelligenceAccessPolicy.model_validate_json(raw)
        identities = [principal.principal_id for principal in policy.principals]
        credentials = [principal.credential_sha256 for principal in policy.principals]
        if len(set(identities)) != len(identities) or len(set(credentials)) != len(credentials):
            raise ValueError
        return policy
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="intelligence_access_policy_unavailable") from exc


def verified_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> IntelligencePrincipal:
    if credentials is None or not 32 <= len(credentials.credentials) <= 256:
        raise HTTPException(
            401, detail="intelligence_credentials_required", headers={"WWW-Authenticate": "Bearer"}
        )
    policy = access_policy()
    digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    if policy is not None:
        for principal in policy.principals:
            if hmac.compare_digest(digest, principal.credential_sha256):
                return principal
    raise HTTPException(
        401, detail="intelligence_credentials_invalid", headers={"WWW-Authenticate": "Bearer"}
    )
