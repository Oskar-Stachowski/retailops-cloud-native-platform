"""Dedicated personal read grants for suggestion scope and pinned decision policy."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field

from app.auth.intelligence import PrivateContract, Sha256, Symbol, read_private_policy

Reference = Annotated[str, Field(min_length=1, max_length=2048)]
bearer = HTTPBearer(auto_error=False, scheme_name="SuggestionCredential")


class SuggestionPrincipal(PrivateContract):
    principal_id: Symbol
    credential_sha256: Sha256
    capabilities: tuple[Literal["suggestion:read"], ...] = Field(min_length=1, max_length=1)
    product_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=20)
    selling_location_ids: tuple[Symbol, ...] = Field(min_length=1, max_length=5)
    channels: tuple[Literal["store", "online"], ...] = Field(min_length=1, max_length=2)
    policy_sha256s: tuple[Sha256, ...] = Field(min_length=1, max_length=32)
    agent_config_versions: tuple[Symbol, ...] = Field(min_length=1, max_length=32)
    model_release_refs: tuple[Reference, ...] = Field(max_length=32)


class SuggestionAccessPolicy(PrivateContract):
    version: Literal["retailops-suggestion-access-1.0"]
    principals: tuple[SuggestionPrincipal, ...] = Field(min_length=1, max_length=32)


def suggestion_access_policy() -> SuggestionAccessPolicy | None:
    raw = read_private_policy("RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY")
    if raw is None:
        return None
    try:
        policy = SuggestionAccessPolicy.model_validate_json(raw)
        ids = [item.principal_id for item in policy.principals]
        digests = [item.credential_sha256 for item in policy.principals]
        if len(ids) != len(set(ids)) or len(digests) != len(set(digests)):
            raise ValueError
        return policy
    except ValueError as exc:
        raise HTTPException(503, detail="intelligence_access_policy_unavailable") from exc


def verified_suggestion_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> SuggestionPrincipal:
    if credentials is not None and 32 <= len(credentials.credentials) <= 256:
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        policy = suggestion_access_policy()
        if policy is not None:
            for principal in policy.principals:
                if hmac.compare_digest(digest, principal.credential_sha256):
                    return principal
    raise HTTPException(
        401, detail="suggestion_credentials_required", headers={"WWW-Authenticate": "Bearer"}
    )
