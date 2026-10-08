"""Receipts must not mutate canonical source storage or private input plans."""

from __future__ import annotations

import pytest

from data.anomalies.run_source import main


@pytest.mark.parametrize("mode", ["generate", "verify", "plan"])
def test_cli_rejects_receipt_over_protected_input_before_any_work(tmp_path, monkeypatch, mode):
    source_root = tmp_path / "sources"
    source = source_root / "source-sha256-parent"
    source.mkdir(parents=True)
    protected = source / "source_report.json"
    protected.write_bytes(b"immutable-source-sentinel\n")
    if mode == "generate":
        arguments = ["--example", "--output-root", str(source_root)]
    elif mode == "verify":
        arguments = ["--verify", str(source)]
    else:
        protected = tmp_path / "private-plan.json"
        protected.write_bytes(b"private-plan-sentinel\n")
        arguments = ["--plan", str(protected), "--output-root", str(source_root)]
    before = protected.read_bytes()
    monkeypatch.setattr("sys.argv", ["run_source", *arguments, "--output", str(protected)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and protected.read_bytes() == before
    assert len(list(source_root.rglob("*"))) == 2
