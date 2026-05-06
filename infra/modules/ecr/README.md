# ECR Module

This module defines the first container registry baseline for the RetailOps AWS foundation.

## Scope

The module creates Amazon ECR repositories for release or release-candidate container images produced by the RetailOps delivery workflow.

Current repositories:

- API image repository,
- frontend image repository.

## Baseline controls

Each repository is configured with:

- immutable image tags,
- scan-on-push enabled,
- AES256 encryption,
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

For the MVP foundation, ECR should primarily hold release and release-candidate images. Short-lived local and CI images can continue to use local Docker tags until the cloud publishing workflow is intentionally enabled.

## Out of scope

This module does not:

- build Docker images,
- push images to ECR,
- authenticate GitHub Actions or Jenkins to ECR,
- create deployment permissions,
- create Kubernetes/EKS deployment resources.

Those capabilities belong to later CI/CD and deployment commits.
