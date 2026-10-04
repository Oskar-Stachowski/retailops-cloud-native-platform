"""Real filesystem sealing and authenticated bytes; this tiny fixture has no ML qualification."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.source_bundles import BundleError, load_manifest, publish, publish_noreplace


@pytest.fixture
def source_bundle(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir(mode=0o700)
    part = snapshot / "facts/sales/part.parquet"
    part.parent.mkdir(parents=True)
    raw = b"explicit-byte-transport-fixture-not-a-valid-parquet"
    part.write_bytes(raw)
    document = {
        "schema_version": "1.2.0",
        "snapshot_id": "snapshot-sha256-" + "a" * 64,
        "source_dataset_id": "source-sha256-" + "b" * 64,
        "descriptor": {"include_evaluation_truth": False},
        "metadata_files": [],
        "tables": [
            {
                "data_class": "source_observation",
                "files": [
                    {
                        "path": "facts/sales/part.parquet",
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ],
            }
        ],
    }
    body = json.dumps(document).encode()
    (snapshot / "snapshot_manifest.json").write_bytes(body)
    (snapshot / "manifest.sha256").write_text(hashlib.sha256(body).hexdigest() + "\n")
    store = tmp_path / "store"
    manifest = publish(snapshot, store)
    token = "explicit-source-bundle-test-credential-0123456789"
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "version": "retailops-source-bundle-access-1.0",
                "principals": [
                    {
                        "principal_id": "bundle-test",
                        "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "bundle_ids": [manifest.bundle_id],
                    }
                ],
            }
        )
    )
    policy.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_SOURCE_BUNDLE_ROOT", str(store))
    monkeypatch.setenv("RETAILOPS_SOURCE_BUNDLE_ACCESS_POLICY", str(policy))
    return snapshot, store, manifest, policy, token, raw


def test_exact_authenticated_manifest_and_bytes(source_bundle):
    _, _, manifest, _, token, raw = source_bundle
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + token}
        base = "/integration/bundles/v1/" + manifest.bundle_id
        response = client.get(base + "/manifest", headers=headers)
        assert response.status_code == 200
        assert response.json() == manifest.model_dump(mode="json")
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["replay_handoff"] is False
        ref = next(r for r in manifest.files if r.path.startswith("facts/"))
        response = client.get(base + "/files/" + ref.file_id, headers=headers)
        assert response.content == raw
        assert response.headers["etag"] == '"' + ref.sha256 + '"'


@pytest.mark.parametrize("credential", [None, "incorrect-bundle-token-credential-0123456789"])
def test_auth_precedes_any_bundle_read(source_bundle, credential):
    _, _, manifest, _, _, _ = source_bundle
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + credential} if credential else {}
        assert (
            client.get(
                "/integration/bundles/v1/" + manifest.bundle_id + "/manifest", headers=headers
            ).status_code
            == 401
        )


def test_bundle_grant_cannot_substitute_bounded_product_read(source_bundle):
    _, _, _, _, token, _ = source_bundle
    with TestClient(app) as client:
        assert (
            client.get(
                "/integration/v2/products", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 401
        )


def test_ungranted_identity_is_denied_before_store_lookup(source_bundle):
    _, _, _, _, token, _ = source_bundle
    with TestClient(app) as client:
        assert (
            client.get(
                "/integration/bundles/v1/source-bundle-sha256-" + "f" * 64 + "/manifest",
                headers={"Authorization": "Bearer " + token},
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "mutation", ["corrupt", "symlink", "hardlink", "permissions", "directory_symlink"]
)
def test_corruption_and_file_escape_fail_closed(source_bundle, tmp_path, mutation):
    _, store, manifest, _, token, raw = source_bundle
    ref = next(r for r in manifest.files if r.path.startswith("facts/"))
    target = store / manifest.bundle_id / ref.path
    outside = tmp_path / "outside"
    outside.write_bytes(raw)
    if mutation == "corrupt":
        target.write_bytes(b"wrong")
    elif mutation == "permissions":
        target.chmod(0o644)
    elif mutation == "directory_symlink":
        target.unlink()
        directory = target.parent
        directory.rmdir()
        directory.symlink_to(tmp_path, target_is_directory=True)
    else:
        target.unlink()
        if mutation == "symlink":
            target.symlink_to(outside)
        else:
            target.hardlink_to(outside)
    with TestClient(app) as client:
        assert (
            client.get(
                "/integration/bundles/v1/" + manifest.bundle_id + "/files/" + ref.file_id,
                headers={"Authorization": "Bearer " + token},
            ).status_code
            == 503
        )


def test_policy_revocation_takes_effect_on_next_request(source_bundle):
    _, _, manifest, policy, token, _ = source_bundle
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + token}
        path = "/integration/bundles/v1/" + manifest.bundle_id + "/manifest"
        assert client.get(path, headers=headers).status_code == 200
        contents = json.loads(policy.read_text())
        contents["principals"][0]["credential_sha256"] = "f" * 64
        policy.write_text(json.dumps(contents))
        assert client.get(path, headers=headers).status_code == 401


def test_concurrent_sealing_reuses_exact_immutable_content(source_bundle):
    snapshot, store, manifest, _, _, _ = source_bundle
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(snapshot, store), range(2)))
    assert results == [manifest, manifest]
    assert load_manifest(store, manifest.bundle_id) == manifest
    assert not list(store.glob(".staging-*"))


@pytest.mark.parametrize("mutation", ["extra_file", "source_corrupt", "source_symlink", "truth"])
def test_failed_sealing_never_publishes_partial_bundle(source_bundle, tmp_path, mutation):
    snapshot, _, _, _, _, _ = source_bundle
    if mutation == "extra_file":
        (snapshot / "unexpected").write_text("private")
    elif mutation == "source_corrupt":
        (snapshot / "facts/sales/part.parquet").write_text("corrupt")
    elif mutation == "source_symlink":
        (snapshot / "unused-symlink").symlink_to(tmp_path, target_is_directory=True)
    else:
        path = snapshot / "snapshot_manifest.json"
        data = json.loads(path.read_text())
        data["descriptor"]["include_evaluation_truth"] = True
        path.write_text(json.dumps(data))
    store = tmp_path / "new-store"
    with pytest.raises((ValueError, OSError)):
        publish(snapshot, store)
    assert not list(store.glob("source-bundle-*"))
    assert not list(store.glob(".staging-*"))


def test_atomic_publication_refuses_even_empty_existing_directory(tmp_path):
    source = tmp_path / "staged"
    source.mkdir()
    (source / "data").write_text("new")
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(OSError):
        publish_noreplace(source, destination)
    assert destination.exists() and not list(destination.iterdir())
    assert (source / "data").read_text() == "new"
