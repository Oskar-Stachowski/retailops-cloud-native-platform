from __future__ import annotations

from pathlib import Path

import pytest

from scripts.seed_demo_data import (
    resolve_seed_data_dir,
    resolve_seed_data_profile,
)


def test_seed_profile_defaults_to_small(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETAILOPS_SEED_DATA_PROFILE", raising=False)
    monkeypatch.delenv("RETAILOPS_SEED_DATA_DIR", raising=False)
    monkeypatch.delenv("RETAILOPS_DEMO_DATA_DIR", raising=False)

    assert resolve_seed_data_profile() == "small"


def test_legacy_demo_data_dir_selects_demo_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETAILOPS_SEED_DATA_PROFILE", raising=False)
    monkeypatch.setenv("RETAILOPS_DEMO_DATA_DIR", "/tmp/retailops-demo")

    assert resolve_seed_data_profile() == "demo"


def test_seed_data_dir_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    monkeypatch.setenv("RETAILOPS_SEED_DATA_PROFILE", "medium")
    monkeypatch.setenv("RETAILOPS_SEED_DATA_DIR", str(seed_dir))

    assert resolve_seed_data_dir() == seed_dir


def test_invalid_seed_profile_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETAILOPS_SEED_DATA_PROFILE", "large")

    with pytest.raises(ValueError, match="Unsupported RETAILOPS_SEED_DATA_PROFILE"):
        resolve_seed_data_profile()
