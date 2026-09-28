from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from data.generator import identity as source_identity
from data.generator.configuration import DatasetGenerationConfig
from data.generator.main import build_dataset
from ml.features import identity as feature_identity
from ml.features.ai_demand import AI_FEATURE_COLUMNS
from ml.features.isolated_runtime import WORKER_FILES


@pytest.mark.parametrize("name", WORKER_FILES)
def test_every_executable_worker_file_changes_identity_and_dirty_provenance(tmp_path, monkeypatch, name):
    fingerprint = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
    assert set(WORKER_FILES) <= fingerprint["code_files"].keys()
    repo = source_identity.ROOT
    for relative in set(fingerprint["code_files"]) | set(fingerprint["dependency_files"]):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, target)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Audit", "-c", "user.email=audit@example.invalid", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    config = DatasetGenerationConfig(profile="ai-smoke", days=1, products=2, stores=1, warehouses=1)
    tables = build_dataset(config)
    descriptor = source_identity.source_identity(config, tables)[1]
    monkeypatch.setattr(source_identity, "ROOT", tmp_path)
    monkeypatch.setattr(feature_identity, "ROOT", tmp_path)
    before = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
    assert source_identity.code_provenance(before)["code_state"] == "clean"
    first = feature_identity.feature_identity_from_source(config, descriptor, [], AI_FEATURE_COLUMNS)[0]
    changed = tmp_path / name
    changed.write_text(changed.read_text() + "\n# changed executable bundle input\n")
    after = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
    second = feature_identity.feature_identity_from_source(config, descriptor, [], AI_FEATURE_COLUMNS)[0]
    assert first != second
    assert before["code_sha256"] != after["code_sha256"]
    assert source_identity.code_provenance(after)["code_state"] == "modified"
