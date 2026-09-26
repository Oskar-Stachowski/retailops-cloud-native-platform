# ruff: noqa: INP001, PT009, PT027, S101
"""Regression checks for drift classification and backend/account boundaries."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plan import ReviewError, bucket_controls, check, classify, summarize_plan, validate_backend


def change(actions: list[str]) -> dict:
    return {"mode": "managed", "type": "aws_vpc", "change": {"actions": actions}}


class PlanTests(unittest.TestCase):
    def test_baseline_is_never_no_drift(self) -> None:
        summary = summarize_plan(
            {"format_version": "1.2", "resource_changes": [change(["create"])]}
        )
        self.assertEqual(classify("baseline", 0, summary, None), "baseline_only_no_state")

    def test_missing_managed_state_cannot_pass_as_no_drift(self) -> None:
        with self.assertRaisesRegex(ReviewError, "no_managed_resources"):
            classify("drift", 0, summarize_plan({"format_version": "1.2"}), None)

    def test_external_drift_is_separate_from_code_changes(self) -> None:
        summary = summarize_plan(
            {"format_version": "1.2", "resource_changes": [change(["update"])]}
        )
        self.assertEqual(classify("drift", 1, summary, None), "configuration_or_output_changes")
        summary["resource_drift"] = [{"type": "aws_vpc", "actions": ["update"], "count": 1}]
        self.assertEqual(classify("drift", 1, summary, None), "drift_detected")

    def test_refresh_only_drift_is_not_lost(self) -> None:
        empty = summarize_plan({"format_version": "1.2"})
        refresh = summarize_plan({"format_version": "1.2", "resource_drift": [change(["delete"])]})
        self.assertEqual(classify("drift", 1, empty, refresh), "drift_detected")

    def test_no_changes(self) -> None:
        self.assertEqual(
            classify("drift", 2, summarize_plan({"format_version": "1.2"}), None), "no_drift"
        )

    def test_output_only_changes_need_review(self) -> None:
        summary = summarize_plan(
            {"format_version": "1.2", "output_changes": {"x": {"actions": ["update"]}}}
        )
        self.assertEqual(classify("drift", 1, summary, None), "configuration_or_output_changes")

    def test_partial_failed_and_unknown_plan_formats_rejected(self) -> None:
        for extra in [
            {"complete": False},
            {"errored": True},
            {"deferred_changes": [{}]},
            {"format_version": "2.0"},
            {"checks": [{"status": "fail"}]},
        ]:
            with self.subTest(extra=extra), self.assertRaises(ReviewError):
                summarize_plan({"format_version": "1.2", **extra})

    def test_summary_cannot_expose_attributes_outputs_or_instance_keys(self) -> None:
        item = change(["delete", "create"])
        item.update(address='aws_vpc.example["PRIVATE-ID"]', index="PRIVATE-ID")
        item["change"]["before"] = {"secret": "PRIVATE-VALUE"}
        plan = {
            "format_version": "1.2",
            "resource_changes": [item],
            "output_changes": {"PRIVATE-OUTPUT": {"actions": ["create"], "after": "PRIVATE-VALUE"}},
        }
        self.assertNotIn("PRIVATE", json.dumps(summarize_plan(plan)))

    def test_account_mismatch_stops_before_terraform(self) -> None:
        args = argparse.Namespace(expected_account_id="000000000000", profile=None)
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("plan.aws", return_value={"Account": "111111111111"}),
            patch("plan.run") as command,
        ):
            with self.assertRaisesRegex(ReviewError, "account_mismatch"):
                check(args, {}, {}, Path(temporary))
            command.assert_not_called()

    def test_backend_requires_locked_encrypted_exact_dev_target(self) -> None:
        config = {
            "bucket": "retailops-test-tfstate",
            "key": "retailops/dev/terraform.tfstate",
            "region": "eu-central-1",
            "kms_key_id": "arn:aws:kms:eu-central-1:000000000000:key/abc-def",
        }
        guarded = validate_backend(config, "000000000000")
        self.assertTrue(guarded["encrypt"] and guarded["use_lockfile"])
        self.assertEqual(guarded["allowed_account_ids"], ["000000000000"])
        for extra in [
            {"use_lockfile": False},
            {"key": "other/state"},
            {"region": "us-east-1"},
            {"bucket": "unrelated"},
            {"kms_key_id": "arn:aws:kms:eu-central-1:111111111111:key/abc-def"},
        ]:
            with self.subTest(extra=extra), self.assertRaises(ReviewError):
                validate_backend({**config, **extra}, "000000000000")

    def test_backend_access_error_is_not_empty_state(self) -> None:
        with (
            patch("plan.aws", side_effect=ReviewError("aws:s3api:exit_255")),
            self.assertRaises(ReviewError),
        ):
            bucket_controls({}, {"bucket": "retailops-test-tfstate"}, "000000000000")

    def test_bucket_controls_reject_weakened_protection(self) -> None:
        bucket = "retailops-test-tfstate"
        key = "arn:aws:kms:eu-central-1:000000000000:key/abc-def"
        arn = "arn:aws:s3:::" + bucket
        responses = {
            "get-bucket-versioning": {"Status": "Enabled"},
            "get-bucket-encryption": {
                "ServerSideEncryptionConfiguration": {
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "aws:kms",
                                "KMSMasterKeyID": key,
                            }
                        }
                    ]
                }
            },
            "get-public-access-block": {
                "PublicAccessBlockConfiguration": dict.fromkeys(
                    [
                        "BlockPublicAcls",
                        "IgnorePublicAcls",
                        "BlockPublicPolicy",
                        "RestrictPublicBuckets",
                    ],
                    True,
                )
            },
            "get-bucket-ownership-controls": {
                "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
            },
            "get-bucket-policy": {
                "Policy": json.dumps(
                    {
                        "Statement": [
                            {
                                "Effect": "Deny",
                                "Principal": "*",
                                "Action": "s3:*",
                                "Resource": [arn, arn + "/*"],
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        ]
                    }
                )
            },
            "head-object": {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": key,
                "VersionId": "version-test",
            },
        }
        config = {"bucket": bucket, "kms_key_id": key}

        def response(_env: dict, *args: str) -> dict:
            return responses[args[1]]

        with patch("plan.aws", side_effect=response):
            self.assertTrue(all(bucket_controls({}, config, "000000000000").values()))
            for operation, replacement in [
                ("get-bucket-versioning", {"Status": "Suspended"}),
                ("get-public-access-block", {"PublicAccessBlockConfiguration": {}}),
                ("get-bucket-policy", {"Policy": json.dumps({"Statement": []})}),
                ("head-object", {"ServerSideEncryption": "AES256"}),
                (
                    "head-object",
                    {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": key, "VersionId": "null"},
                ),
            ]:
                previous = responses[operation]
                responses[operation] = replacement
                with self.subTest(operation=operation), self.assertRaises(ReviewError):
                    bucket_controls({}, config, "000000000000")
                responses[operation] = previous


if __name__ == "__main__":
    unittest.main()
