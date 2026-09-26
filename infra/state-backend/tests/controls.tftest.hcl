mock_provider "aws" {}

variables {
  expected_account_id = "000000000000"
  bucket_name         = "retailops-test-tfstate"
}

run "state_controls" {
  command = apply

  assert {
    condition     = aws_s3_bucket.state.force_destroy == false
    error_message = "State bucket must not be emptied by destroy."
  }
  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State recovery requires version history."
  }
  assert {
    condition     = aws_kms_key.state.enable_key_rotation && aws_kms_key.state.deletion_window_in_days == 30
    error_message = "KMS rotation and a recovery window are required."
  }
  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.state.block_public_acls,
      aws_s3_bucket_public_access_block.state.block_public_policy,
      aws_s3_bucket_public_access_block.state.ignore_public_acls,
      aws_s3_bucket_public_access_block.state.restrict_public_buckets
    ])
    error_message = "State must never have public access."
  }
  assert {
    condition     = aws_s3_bucket_ownership_controls.state.rule[0].object_ownership == "BucketOwnerEnforced"
    error_message = "ACLs must be disabled."
  }

  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.state.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    error_message = "State must be encrypted with KMS."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.plan_state_policy).Statement :
      !contains(statement.Action, "s3:PutObject") || statement.Resource == ["${aws_s3_bucket.state.arn}/retailops/dev/terraform.tfstate.tflock"]
    ])
    error_message = "The plan role may write only the exact lock object, never state."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.operator_state_policy).Statement :
      !contains(statement.Action, "s3:DeleteObject") || statement.Resource == ["${aws_s3_bucket.state.arn}/retailops/dev/terraform.tfstate.tflock"]
    ])
    error_message = "Neither role may delete a state object."
  }
}

run "reject_wrong_account_format" {
  command = plan
  variables {
    expected_account_id = "not-an-account"
  }
  expect_failures = [var.expected_account_id]
}
