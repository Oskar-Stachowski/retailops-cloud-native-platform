# ruff: noqa: INP001, S603, EM101, EM102, T201
"""Run a guarded, isolated Terraform baseline or remote-state drift check."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGION = "eu-central-1"
STATE_KEY = "retailops/dev/terraform.tfstate"


class ReviewError(RuntimeError):
    """A classified failure safe to expose without provider output."""


def run(command: list[str], env: dict, *, accepted: tuple = (0,)) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=600, check=False
    )
    if result.returncode not in accepted:
        # Provider diagnostics and plans can contain secrets or account identifiers.
        operation = (
            command[1]
            if command[0] == "aws"
            else next((arg for arg in command[1:] if not arg.startswith("-")), "command")
        )
        raise ReviewError(f"{Path(command[0]).name}:{operation}:exit_{result.returncode}")
    return result


def aws(env: dict, *args: str) -> dict:
    return json.loads(
        run(["aws", *args, "--region", REGION, "--output", "json", "--no-cli-pager"], env).stdout
    )


def validate_backend(config: dict, account: str) -> dict:
    if set(config) != {"bucket", "key", "region", "kms_key_id"}:
        raise ReviewError("backend_configuration_fields_invalid")
    if not all(isinstance(value, str) for value in config.values()):
        raise ReviewError("backend_configuration_types_invalid")
    if (
        not re.fullmatch(r"retailops-[a-z0-9-]+-tfstate", config["bucket"])
        or len(config["bucket"]) > 63
    ):
        raise ReviewError("backend_bucket_name_invalid")
    if config["key"] != STATE_KEY or config["region"] != REGION:
        raise ReviewError("backend_target_invalid")
    if not re.fullmatch(rf"arn:aws:kms:{REGION}:{account}:key/[0-9a-f-]+", config["kms_key_id"]):
        raise ReviewError("backend_kms_account_or_region_invalid")
    return {**config, "encrypt": True, "use_lockfile": True, "allowed_account_ids": [account]}


def bucket_controls(env: dict, config: dict, account: str) -> dict:
    args = ("--bucket", config["bucket"], "--expected-bucket-owner", account)
    versioning = aws(env, "s3api", "get-bucket-versioning", *args)
    encryption = aws(env, "s3api", "get-bucket-encryption", *args)
    public = aws(env, "s3api", "get-public-access-block", *args)
    ownership = aws(env, "s3api", "get-bucket-ownership-controls", *args)
    policy = json.loads(aws(env, "s3api", "get-bucket-policy", *args)["Policy"])
    rules = encryption["ServerSideEncryptionConfiguration"]["Rules"]
    bucket_arn = "arn:aws:s3:::" + config["bucket"]
    tls = any(
        statement.get("Effect") == "Deny"
        and statement.get("Principal") in ("*", {"AWS": "*"})
        and statement.get("Action") in ("s3:*", ["s3:*"])
        and {bucket_arn, bucket_arn + "/*"}.issubset(set(statement.get("Resource", [])))
        and statement.get("Condition")
        in ({"Bool": {"aws:SecureTransport": "false"}}, {"Bool": {"aws:SecureTransport": False}})
        for statement in policy.get("Statement", [])
    )
    checks = {
        "versioning": versioning.get("Status") == "Enabled",
        "kms_encryption": bool(rules)
        and all(
            rule["ApplyServerSideEncryptionByDefault"].get("SSEAlgorithm") == "aws:kms"
            and rule["ApplyServerSideEncryptionByDefault"].get("KMSMasterKeyID")
            == config["kms_key_id"]
            for rule in rules
        ),
        "public_access_block": all(
            public["PublicAccessBlockConfiguration"].get(key) is True
            for key in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ),
        "owner_enforced": any(
            rule.get("ObjectOwnership") == "BucketOwnerEnforced"
            for rule in ownership["OwnershipControls"]["Rules"]
        ),
        "tls_required": tls,
    }
    if not all(checks.values()):
        raise ReviewError(
            "backend_controls_failed:" + ",".join(key for key, value in checks.items() if not value)
        )
    # Missing state and access-denied both fail; neither is treated as empty/no drift.
    head = aws(env, "s3api", "head-object", *args, "--key", STATE_KEY)
    if (
        head.get("ServerSideEncryption") != "aws:kms"
        or head.get("SSEKMSKeyId") != config["kms_key_id"]
    ):
        raise ReviewError("state_object_encryption_invalid")
    if not head.get("VersionId") or head["VersionId"] == "null":
        raise ReviewError("state_object_version_missing")
    checks["state_object_versioned"] = True
    return checks


def summarize_plan(plan: dict) -> dict:
    if str(plan.get("format_version", "")).split(".")[0] != "1" or plan.get("errored") is True:
        raise ReviewError("plan_format_or_execution_invalid")
    if plan.get("complete") is False or plan.get("deferred_changes"):
        raise ReviewError("plan_incomplete")
    if any(check.get("status") == "fail" for check in plan.get("checks", [])):
        raise ReviewError("plan_checks_failed")

    def changes(key: str) -> list[dict]:
        counts = Counter(
            (item["type"], tuple(item["change"]["actions"]))
            for item in plan.get(key, [])
            if item.get("mode") == "managed" and item["change"]["actions"] != ["no-op"]
        )
        return [
            {"type": kind, "actions": list(actions), "count": count}
            for (kind, actions), count in sorted(counts.items())
        ]

    return {
        "resource_changes": changes("resource_changes"),
        "resource_drift": changes("resource_drift"),
        "output_changes": sum(
            value.get("actions") != ["no-op"] for value in plan.get("output_changes", {}).values()
        ),
    }


def classify(mode: str, managed_instances: int, normal: dict, refresh: dict | None) -> str:
    if mode == "baseline":
        return "baseline_only_no_state"
    if managed_instances <= 0:
        raise ReviewError("remote_state_has_no_managed_resources")
    if normal["resource_drift"] or (refresh and refresh["resource_drift"]):
        return "drift_detected"
    if (
        normal["resource_changes"]
        or normal["output_changes"]
        or (refresh and refresh["output_changes"])
    ):
        return "configuration_or_output_changes"
    return "no_drift"


def copy_configuration(destination: Path, env: dict) -> str:
    tracked = run(["git", "-C", str(ROOT), "ls-files", "-z", "infra"], env).stdout.split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, tracked)):
        relative = Path(name)
        if relative.suffix != ".tf" and relative.name not in (
            ".terraform.lock.hcl",
            "terraform.tfvars.example",
        ):
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        if source.is_symlink():
            raise ReviewError("configuration_symlink_not_supported")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        target.write_bytes(content)
        digest.update(name.encode() + b"\0" + content)
    return digest.hexdigest()


def check(args: argparse.Namespace, report: dict, env: dict, work: Path) -> None:  # noqa: PLR0915 -- owns one isolated plan lifecycle
    expected = args.expected_account_id
    if not re.fullmatch(r"[0-9]{12}", expected or ""):
        raise ReviewError("expected_account_id_required")
    if args.profile:
        env["AWS_PROFILE"] = args.profile
    identity = aws(env, "sts", "get-caller-identity")
    if identity["Account"] != expected:
        raise ReviewError("aws_account_mismatch")
    report["account_verified"] = True
    version = json.loads(run([args.terraform, "version", "-json"], env).stdout)["terraform_version"]
    numbers = tuple(int(part) for part in version.split(".")[:2])
    if not (1, 10) <= numbers < (2, 0):
        raise ReviewError("terraform_1_10_or_newer_required")
    report["terraform_version"] = version
    report["configuration_sha256"] = copy_configuration(work, env)
    directory = work / "infra/environments/dev"
    env["TF_DATA_DIR"] = str(work / "terraform-data")
    env["TF_WORKSPACE"] = "default"
    override = {"provider": {"aws": {"region": REGION, "allowed_account_ids": [expected]}}}
    (directory / "account_guard_override.tf.json").write_text(json.dumps(override))
    if args.mode == "drift":
        if not args.backend_config:
            raise ReviewError("backend_config_required_for_drift")
        config = validate_backend(json.loads(args.backend_config.read_text()), expected)
        report["backend_controls"] = bucket_controls(env, config, expected)
        (directory / "backend.tf.json").write_text(
            json.dumps({"terraform": {"backend": {"s3": config}}})
        )
    tf = [args.terraform, f"-chdir={directory}"]
    run([*tf, "init", "-input=false", "-no-color", "-lockfile=readonly"], env)
    run([*tf, "validate", "-no-color"], env)
    state_before = None
    managed = 0
    if args.mode == "drift":
        state_before = json.loads(run([*tf, "state", "pull"], env).stdout)
        managed = sum(
            len(resource.get("instances", []))
            for resource in state_before.get("resources", [])
            if resource.get("mode") == "managed"
        )
        if managed == 0:
            raise ReviewError("remote_state_has_no_managed_resources")
    report["managed_instances_before"] = managed
    results = {}
    for name in ["refresh_only", "normal"] if args.mode == "drift" else ["normal"]:
        plan_path = work / f"{name}.tfplan"
        command = [
            *tf,
            "plan",
            "-input=false",
            "-no-color",
            "-detailed-exitcode",
            "-lock-timeout=30s",
            "-var-file=terraform.tfvars.example",
            f"-out={plan_path}",
        ]
        if name == "refresh_only":
            command.append("-refresh-only")
        result = run(command, env, accepted=(0, 2))
        plan = json.loads(run([*tf, "show", "-json", str(plan_path)], env).stdout)
        results[name] = {"terraform_exit_code": result.returncode, **summarize_plan(plan)}
    if state_before is not None:
        state_after = json.loads(run([*tf, "state", "pull"], env).stdout)
        if state_before != state_after:
            raise ReviewError("remote_state_changed_during_plan_review")
        report["remote_state_unchanged"] = True
    report["plans"] = results
    report["classification"] = classify(
        args.mode, managed, results["normal"], results.get("refresh_only")
    )
    report["status"] = "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "drift"), required=True)
    parser.add_argument("--expected-account-id", default=os.environ.get("TF_EXPECTED_ACCOUNT_ID"))
    parser.add_argument("--profile")
    parser.add_argument("--backend-config", type=Path)
    parser.add_argument("--terraform", default=shutil.which("terraform") or "terraform")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "ci-cd/reports/terraform-state")
    args = parser.parse_args()
    os.umask(0o077)
    report_path = args.reports_dir.resolve() / uuid.uuid4().hex[:12] / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("TF_CLI_ARGS", "TF_VAR_", "TF_LOG"))
    }
    env.update(
        {
            "TF_IN_AUTOMATION": "true",
            "TF_INPUT": "false",
            "AWS_REGION": REGION,
            "AWS_DEFAULT_REGION": REGION,
            "AWS_PAGER": "",
        }
    )
    report = {
        "status": "failed",
        "mode": args.mode,
        "region": REGION,
        "started_at": datetime.now(UTC).isoformat(),
        "source_commit": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], env).stdout.strip(),
        "working_tree_dirty": bool(
            run(["git", "-C", str(ROOT), "status", "--porcelain"], env).stdout.strip()
        ),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ci_run_url": f"https://github.com/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
        if env.get("GITHUB_RUN_ID")
        else None,
        "scope": "plan only; no apply, refresh, import, state push, migration or resource deletion",
    }
    temporary = None
    try:
        with tempfile.TemporaryDirectory(prefix="retailops-tf-plan-") as temporary:
            check(args, report, env, Path(temporary))
    except ReviewError as error:
        report["status"] = "failed"
        report["error"] = str(error)
    except Exception as error:  # noqa: BLE001 -- safe report; do not expose provider/config contents
        report["status"] = "failed"
        report["error"] = type(error).__name__
    report["private_artifacts_removed"] = temporary is None or not Path(temporary).exists()
    report["finished_at"] = datetime.now(UTC).isoformat()
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "classification": report.get("classification"),
                "error": report.get("error"),
                "report": str(report_path),
            }
        )
    )
    if report["status"] != "passed":
        return 1
    return (
        2
        if report["classification"] in ("drift_detected", "configuration_or_output_changes")
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
