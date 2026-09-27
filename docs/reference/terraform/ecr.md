# ECR Module

This module defines the first container registry baseline for the RetailOps AWS foundation.

## Scope

The module defines Amazon ECR repositories. It does not publish images.
Current registry releases use GHCR through the
[release workflow](../../governance/releases.md); publishing to ECR is a separate
cloud integration.

The dev configuration declares repositories for:

- API image repository,
- frontend image repository.

## Baseline controls

Each repository is configured with:

- immutable image tags,
- scan-on-push enabled,
- KMS encryption using the AWS-managed ECR key (no custom key is supplied),
- lifecycle policy limiting retained images,
- common governance and FinOps tags inherited from the shared tags module.

## Naming

The module intentionally creates repository names without an additional `-ecr` suffix because the AWS resource type already communicates that these are ECR repositories.

Example names:

```text
retailops-dev-api
retailops-dev-frontend
```

## Cost and lifecycle policy

The lifecycle policy keeps only a controlled number of latest images. This avoids storing unlimited old CI or release images in the registry.

The policy expires images by count across all tags. Before ECR becomes a runtime
registry, verify that retention preserves the active and rollback digests;
count-based retention alone does not protect them.

## Out of scope

This module does not:

- build Docker images,
- push images to ECR,
- authenticate GitHub Actions or Jenkins to ECR,
- create deployment permissions,
- create Kubernetes/EKS deployment resources.

Cloud integration follows the [AWS activation plan](../../plans/aws-activation.md).
