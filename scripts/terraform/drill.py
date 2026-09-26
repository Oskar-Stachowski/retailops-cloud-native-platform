# ruff: noqa: INP001, S101, S603, T201, PT018
"""Verify real Terraform plan semantics and local state migration without AWS."""

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from plan import ROOT, classify, run, summarize_plan


def main() -> None:  # noqa: PLR0915 -- ordered local integration drill
    os.umask(0o077)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("AWS_", "TF_"))}
    env.update({"TF_IN_AUTOMATION": "true", "TF_INPUT": "false"})
    report = {
        "status": "failed",
        "scope": "local_file fixture; no AWS resources or S3 backend",
        "started_at": datetime.now(UTC).isoformat(),
        "source_commit": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], env).stdout.strip(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    report_path = ROOT / "ci-cd/reports/terraform-state/contract-drill.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="retailops-tf-contract-") as temporary:
            directory = Path(temporary)
            for source in (Path(__file__).parent / "fixtures").iterdir():
                if source.name in ("main.tf", ".terraform.lock.hcl"):
                    shutil.copyfile(source, directory / source.name)
            tf = [shutil.which("terraform") or "terraform", f"-chdir={directory}"]
            run([*tf, "init", "-input=false", "-no-color", "-lockfile=readonly"], env)

            def plan(name: str, *, refresh: bool = False) -> dict:
                command = [
                    *tf,
                    "plan",
                    "-input=false",
                    "-no-color",
                    "-detailed-exitcode",
                    f"-out={directory / (name + '.tfplan')}",
                ]
                if refresh:
                    command.append("-refresh-only")
                result = run(command, env, accepted=(0, 2))
                value = json.loads(
                    run([*tf, "show", "-json", str(directory / (name + ".tfplan"))], env).stdout
                )
                return {"terraform_exit_code": result.returncode, **summarize_plan(value)}

            baseline = plan("baseline")
            assert baseline["terraform_exit_code"] == 2
            assert classify("baseline", 0, baseline, None) == "baseline_only_no_state"
            run(
                [*tf, "apply", "-input=false", "-no-color", str(directory / "baseline.tfplan")], env
            )
            initial = json.loads(run([*tf, "state", "pull"], env).stdout)
            clean = plan("clean")
            assert (
                clean["terraform_exit_code"] == 0
                and classify("drift", 1, clean, None) == "no_drift"
            )
            # The entire source, destination, data and backend belong to this temporary fixture.
            destination = directory / "migrated.tfstate"
            (directory / "backend.tf.json").write_text(
                json.dumps({"terraform": {"backend": {"local": {"path": str(destination)}}}})
            )
            run([*tf, "init", "-migrate-state", "-force-copy", "-input=false", "-no-color"], env)
            migrated = json.loads(run([*tf, "state", "pull"], env).stdout)
            assert (
                migrated["lineage"] == initial["lineage"]
                and migrated["resources"] == initial["resources"]
            )
            before_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
            (directory / "fixture.txt").write_text("externally changed")
            external = plan("external", refresh=True)
            assert external["terraform_exit_code"] == 2
            assert classify("drift", 1, clean, external) == "drift_detected"
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == before_hash
            (directory / "fixture.txt").write_text("original")
            config = directory / "main.tf"
            config.write_text(
                config.read_text().replace('"original"', '"changed by configuration"')
            )
            config_change = plan("configuration")
            assert config_change["terraform_exit_code"] == 2
            assert classify("drift", 1, config_change, None) == "configuration_or_output_changes"
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == before_hash
            report.update(
                status="passed",
                baseline=baseline,
                clean=clean,
                external_change=external,
                configuration_change=config_change,
                local_migration_preserved_state=True,
                plans_left_state_unchanged=True,
            )
        report["cleanup"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        raise
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Terraform contract drill passed: {report_path}")


if __name__ == "__main__":
    main()
