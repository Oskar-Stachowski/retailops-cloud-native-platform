"""Whole-bundle grants are explicit and separate from bounded product reads."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field

from app.auth.intelligence import PrivateContract, Sha256, Symbol
from app.services.source_bundle_wire import BundleID, canonical
from app.services.source_bundles import decode, read_confined

bearer = HTTPBearer(auto_error=False, scheme_name="SourceBundleCredential")


class BundlePrincipal(PrivateContract):
    principal_id: Symbol
    credential_sha256: Sha256
    bundle_ids: tuple[BundleID, ...] = Field(min_length=1, max_length=128)


class BundlePolicy(PrivateContract):
    version: Literal["retailops-source-bundle-access-1.0"]
    principals: tuple[BundlePrincipal, ...] = Field(min_length=1, max_length=32)


def verified_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> BundlePrincipal:
    if credentials is None or not 32 <= len(credentials.credentials) <= 256:
        raise HTTPException(401, detail="bundle_credentials_required")
    value = os.getenv("RETAILOPS_SOURCE_BUNDLE_ACCESS_POLICY")
    if value:
        try:
            path = Path(value)
            policy = BundlePolicy.model_validate_json(
                canonical(decode(read_confined(path.parent, path.name, 65536)))
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(503, detail="bundle_policy_unavailable") from exc
        digests = [principal.credential_sha256 for principal in policy.principals]
        names = [principal.principal_id for principal in policy.principals]
        if len(set(digests)) != len(digests) or len(set(names)) != len(names):
            raise HTTPException(503, detail="bundle_policy_unavailable")
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        for principal in policy.principals:
            if hmac.compare_digest(digest, principal.credential_sha256):
                return principal
    raise HTTPException(401, detail="bundle_credentials_invalid")
