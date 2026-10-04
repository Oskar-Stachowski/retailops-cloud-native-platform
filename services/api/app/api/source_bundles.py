"""Authenticated immutable source files; no inference of broker replay support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth.source_bundles import BundlePrincipal, verified_principal
from app.services.source_bundle_wire import BundleID, BundleManifest, Digest
from app.services.source_bundles import file_bytes, load_manifest

router = APIRouter(prefix="/integration/bundles/v1", tags=["source-bundles"])
Principal = Annotated[BundlePrincipal, Depends(verified_principal)]


def context(bundle_id: str, principal: BundlePrincipal) -> tuple[Path, BundleManifest]:
    if bundle_id not in principal.bundle_ids:
        raise HTTPException(403, detail="bundle_scope_denied")
    configured = os.getenv("RETAILOPS_SOURCE_BUNDLE_ROOT")
    if not configured:
        raise HTTPException(503, detail="bundle_store_unavailable")
    root = Path(configured)
    try:
        return root, load_manifest(root, bundle_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail="bundle_not_found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="bundle_store_unavailable") from exc


@router.get("/{bundle_id}/manifest", response_model=BundleManifest)
def manifest(bundle_id: BundleID, principal: Principal, response: Response) -> BundleManifest:
    _, result = context(bundle_id, principal)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{bundle_id}/files/{file_id}", response_class=Response)
def artifact(bundle_id: BundleID, file_id: Digest, principal: Principal) -> Response:
    root, result = context(bundle_id, principal)
    try:
        raw, reference = file_bytes(root, result, file_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail="bundle_file_not_found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="bundle_file_unavailable") from exc
    return Response(
        raw,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store", "ETag": '"' + reference.sha256 + '"'},
    )
