data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  flow_log_group_name = "/aws/vpc/${var.name_prefix}/flow-logs"
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_support   = var.enable_dns_support
  enable_dns_hostnames = var.enable_dns_hostnames

  tags = {
    Name = "${var.name_prefix}-network-vpc"
  }
}

resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  ingress = []
  egress  = []

  tags = {
    Name = "${var.name_prefix}-network-default-sg-restricted"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-network-igw"
  }
}

resource "aws_subnet" "public" {
  for_each = var.public_subnets

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-network-public-subnet-${each.key}"
  }
}

resource "aws_subnet" "private" {
  for_each = var.private_subnets

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-network-private-subnet-${each.key}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.name_prefix}-network-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = var.private_subnets

  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-network-private-rt-${each.key}"
  }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

resource "aws_kms_key" "vpc_flow_logs" {
  description             = "KMS key for ${var.name_prefix} VPC Flow Logs"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableAccountKeyAdministration"
        Effect = "Allow"
        Principal = {
          AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogsEncryption"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.id}.${data.aws_partition.current.dns_suffix}"
        }
        Action = [
          "kms:Decrypt*",
          "kms:Describe*",
          "kms:Encrypt*",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*",
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:${local.flow_log_group_name}"
          }
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
    ]
  })

  tags = {
    Name = "${var.name_prefix}-network-flow-logs"
  }
}

resource "aws_kms_alias" "vpc_flow_logs" {
  name          = "alias/${var.name_prefix}-network-flow-logs"
  target_key_id = aws_kms_key.vpc_flow_logs.key_id
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = local.flow_log_group_name
  retention_in_days = var.flow_log_retention_in_days
  kms_key_id        = aws_kms_key.vpc_flow_logs.arn

  tags = {
    Name = "${var.name_prefix}-network-flow-logs"
  }
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "${var.name_prefix}-network-flow-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowVpcFlowLogsService"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
    ]
  })

  tags = {
    Name = "${var.name_prefix}-network-flow-logs"
  }
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "${var.name_prefix}-network-flow-logs"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteVpcFlowLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.vpc_flow_logs.arn}:*"
      },
      {
        Sid      = "DescribeVpcFlowLogStreams"
        Effect   = "Allow"
        Action   = "logs:DescribeLogStreams"
        Resource = aws_cloudwatch_log_group.vpc_flow_logs.arn
      },
      {
        Sid      = "DiscoverVpcFlowLogGroup"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
    ]
  })
}

resource "aws_flow_log" "this" {
  vpc_id                   = aws_vpc.this.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.vpc_flow_logs.arn
  iam_role_arn             = aws_iam_role.vpc_flow_logs.arn
  max_aggregation_interval = 60

  tags = {
    Name = "${var.name_prefix}-network-vpc-flow-log"
  }

  depends_on = [aws_iam_role_policy.vpc_flow_logs]
}
