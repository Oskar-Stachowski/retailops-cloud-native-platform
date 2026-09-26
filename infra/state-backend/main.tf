terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "expected_account_id" {
  type        = string
  description = "Explicit target account; supply privately, never infer from the default profile."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Supply the 12-digit target account ID."
  }
}

variable "bucket_name" {
  type        = string
  description = "Unique persistent state bucket, separate from disposable application resources."
  validation {
    condition     = can(regex("^retailops-[a-z0-9-]+-tfstate$", var.bucket_name)) && length(var.bucket_name) <= 63
    error_message = "Use a unique retailops-...-tfstate bucket name of at most 63 characters."
  }
}

provider "aws" {
  region              = "eu-central-1"
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project     = "retailops"
      Environment = "dev"
      ManagedBy   = "terraform"
      Lifecycle   = "persistent"
      Component   = "terraform-state"
    }
  }
}

resource "aws_kms_key" "state" {
  description             = "RetailOps persistent Terraform state encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "state" {
  # checkov:skip=CKV_AWS_18:Dedicated access-log destination is not provisioned by this unactivated dev bootstrap; review before production.
  # checkov:skip=CKV_AWS_144:Cross-region replication is outside the local/dev recovery target; versioning is required and tested.
  # checkov:skip=CKV2_AWS_62:No notification consumer exists for this unactivated dev backend; activation review must define monitoring.
  bucket        = var.bucket_name
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  # No current or noncurrent state versions expire automatically.
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

locals {
  state_key = "retailops/dev/terraform.tfstate"
  state_arn = "${aws_s3_bucket.state.arn}/${local.state_key}"
  lock_arn  = "${local.state_arn}.tflock"
  plan_statements = [
    { Sid = "ReadBucketLocation", Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = [aws_s3_bucket.state.arn] },
    { Sid = "ListStatePrefix", Effect = "Allow", Action = ["s3:ListBucket"], Resource = [aws_s3_bucket.state.arn], Condition = { StringLike = { "s3:prefix" = [local.state_key, "${local.state_key}.tflock", "env:/"] } } },
    { Sid = "ReadState", Effect = "Allow", Action = ["s3:GetObject"], Resource = [local.state_arn] },
    { Sid = "ManageOnlyStateLock", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = [local.lock_arn] },
    { Sid = "StateEncryption", Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"], Resource = [aws_kms_key.state.arn], Condition = { StringEquals = { "kms:ViaService" = "s3.eu-central-1.amazonaws.com" } } },
    { Sid = "InspectBucketControls", Effect = "Allow", Action = ["s3:GetBucketVersioning", "s3:GetEncryptionConfiguration", "s3:GetBucketPublicAccessBlock", "s3:GetBucketOwnershipControls", "s3:GetBucketPolicy"], Resource = [aws_s3_bucket.state.arn] }
  ]
}

output "backend_config" {
  description = "Noncredential configuration for the guarded plan runner; keep account-specific values local."
  value = {
    bucket     = aws_s3_bucket.state.id
    key        = local.state_key
    region     = "eu-central-1"
    kms_key_id = aws_kms_key.state.arn
  }
}

output "plan_state_policy" {
  description = "Attach only after reviewing activation; grants lock writes but no state writes or deletes."
  value       = jsonencode({ Version = "2012-10-17", Statement = local.plan_statements })
}

output "operator_state_policy" {
  description = "Separate operator access for migration/apply; no state deletion permission."
  value = jsonencode({ Version = "2012-10-17", Statement = concat(local.plan_statements, [
    { Sid = "WriteState", Effect = "Allow", Action = ["s3:PutObject"], Resource = [local.state_arn] }
  ]) })
}
