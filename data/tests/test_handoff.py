"""The bounded current fixture is a frozen projection of the qualified exporter."""

import json
import shutil

import pytest

from data.export.policy import GENERATED_ROOT, ROOT, fixture_budget, generated_target
from data.handoff.fixture import FIXTURE_ROOT, expected_manifest, package_fixture, verify_handoff


def test_full_reviewed_fixture_and_typed_parity():
    expected = verify_handoff(FIXTURE_ROOT)
    assert expected["table_count"] == 25
    assert expected["rows"] == 31171
    assert len(expected["files"]) == 74
    assert expected["readiness"]["forecast_source"] == "ready"
    assert expected["inventory_ready"] is False
    assert not (FIXTURE_ROOT / "snapshot/evaluation_truth").exists()


def test_fixture_remains_bounded_and_protected_from_cleanup():
    report = fixture_budget()
    assert report["current_fixtures"] == 1
    assert report["unpacked_bytes"] == 4484021
    with pytest.raises(ValueError):
        generated_target(FIXTURE_ROOT)


def test_package_reproduction_preserves_frozen_bytes(tmp_path):
    target = GENERATED_ROOT / ("handoff-test-" + tmp_path.name)
    result = package_fixture(FIXTURE_ROOT / "snapshot", target)
    try:
        assert result["package_bytes"] == 2048665
        assert (target / "expected_manifest.json").read_bytes() == (FIXTURE_ROOT / "expected_manifest.json").read_bytes()
        with pytest.raises(ValueError, match="already exists"):
            package_fixture(FIXTURE_ROOT / "snapshot", target)
    finally:
        shutil.rmtree(target)


@pytest.mark.parametrize("fault", ["extra", "expected", "contract", "missing", "symlink"])
def test_handoff_faults_fail(tmp_path, fault):
    shutil.copytree(FIXTURE_ROOT, tmp_path / "package")
    package = tmp_path / "package"
    if fault == "extra":
        (package / "extra.json").write_text("{}")
    elif fault == "expected":
        path = package / "expected_manifest.json"
        payload = json.loads(path.read_text())
        payload["rows"] += 1
        path.write_text(json.dumps(payload))
    elif fault == "contract":
        path = package / "contract.json"
        payload = json.loads(path.read_text())
        payload["contract_version"] = "9.0.0"
        path.write_text(json.dumps(payload))
    elif fault == "missing":
        (package / "snapshot/manifest.sha256").unlink()
    elif fault == "symlink":
        path = package / "contract.json"
        path.unlink()
        path.symlink_to(ROOT / "data/contracts/source_snapshot_handoff.v1.json")
    with pytest.raises((ValueError, OSError)):
        verify_handoff(package)
