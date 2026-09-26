# ruff: noqa: INP001, EM101, T201
"""Read the dev account inventory without exposing resource IDs or state contents."""

import hashlib
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from plan import REGION, ROOT, ReviewError, aws, run


def main() -> int:
    env = dict(os.environ)
    account = env.get("TF_EXPECTED_ACCOUNT_ID", "")
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ReviewError("expected_account_id_required")
    if aws(env, "sts", "get-caller-identity")["Account"] != account:
        raise ReviewError("aws_account_mismatch")
    queries = {
        "tagged_resources": (
            [
                "resourcegroupstaggingapi",
                "get-resources",
                "--tag-filters",
                "Key=Project,Values=retailops",
            ],
            "ResourceTagMappingList",
            None,
        ),
        "vpcs_by_project": (
            ["ec2", "describe-vpcs", "--filters", "Name=tag:Project,Values=retailops"],
            "Vpcs",
            None,
        ),
        "vpcs_by_name": (
            ["ec2", "describe-vpcs", "--filters", "Name=tag:Name,Values=retailops-*"],
            "Vpcs",
            None,
        ),
        "ecr": (["ecr", "describe-repositories"], "repositories", "repositoryName"),
        "iam_policies": (["iam", "list-policies", "--scope", "Local"], "Policies", "PolicyName"),
        "iam_roles": (["iam", "list-roles"], "Roles", "RoleName"),
        "application_logs": (
            ["logs", "describe-log-groups", "--log-group-name-prefix", "/retailops/"],
            "logGroups",
            None,
        ),
        "flow_logs": (
            ["logs", "describe-log-groups", "--log-group-name-prefix", "/aws/vpc/retailops"],
            "logGroups",
            None,
        ),
        "budgets": (
            ["budgets", "describe-budgets", "--account-id", account],
            "Budgets",
            "BudgetName",
        ),
        "kms_aliases": (["kms", "list-aliases"], "Aliases", "AliasName"),
        "state_buckets": (["s3api", "list-buckets"], "Buckets", "Name"),
    }
    results = {}
    role_details = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = {name: executor.submit(aws, env, *query[0]) for name, query in queries.items()}
        for name, future in pending.items():
            try:
                value = future.result()
                _, key, field = queries[name]
                matches = [
                    item
                    for item in value[key]
                    if field is None
                    or "retailops" in item[field].lower()
                    or (
                        name == "state_buckets"
                        and any(
                            token in item[field].lower() for token in ("tfstate", "terraform-state")
                        )
                    )
                ]
                results[name] = {"status": "read", "matching_resources": len(matches)}
                if name == "state_buckets":
                    results[name]["total_buckets_listed"] = len(value[key])
                if name == "iam_roles":
                    for role in matches:
                        role_name = role["RoleName"]
                        policies = aws(
                            env, "iam", "list-attached-role-policies", "--role-name", role_name
                        )
                        inline = aws(env, "iam", "list-role-policies", "--role-name", role_name)
                        role_details.append(
                            {
                                "role_name": role_name,
                                "attached_policy_names": [
                                    policy["PolicyName"] for policy in policies["AttachedPolicies"]
                                ],
                                "inline_policy_count": len(inline["PolicyNames"]),
                            }
                        )
            except Exception as error:  # noqa: BLE001 -- preserve each failed read without provider details
                results[name] = {"status": "unverified", "error_type": type(error).__name__}
    report = {
        "status": "complete"
        if all(value["status"] == "read" for value in results.values())
        else "partial",
        "captured_at": datetime.now(UTC).isoformat(),
        "region": REGION,
        "account_verified": True,
        "source_commit": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], env).stdout.strip(),
        "working_tree_dirty": bool(
            run(["git", "-C", str(ROOT), "status", "--porcelain"], env).stdout.strip()
        ),
        "configuration": "RetailOps Project/Name tags and name prefixes; IAM/S3 queries have account-wide scope",
        "limits": "Not an all-region cost audit. Untagged or differently named resources/state may exist; no bucket objects are read by discovery.",
        "results": results,
        "roles": role_details,
        "harness_sha256": hashlib.sha256(
            (ROOT / "scripts/terraform/inventory.py").read_bytes()
        ).hexdigest(),
        "aws_mutations": 0,
    }
    path = ROOT / "ci-cd/reports/terraform-state" / uuid.uuid4().hex[:12] / "inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(path)}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
