**Implementation Status:** Mixed. The Terraform AWS foundation is implemented and validated as code, but the downstream workload runtime shown as future architecture is still target scope.
**Legend:** `Implemented` = working in this repository, `Partially implemented` = some code/config/evidence exists, `Target` = design direction only.

```mermaid
flowchart TB
    classDef local fill:#eef2ff,stroke:#4f46e5,stroke-width:1px,color:#111;
    classDef ci fill:#fff7ed,stroke:#ea580c,stroke-width:1px,color:#111;
    classDef tf fill:#f8fafc,stroke:#475569,stroke-width:1px,color:#111;
    classDef aws fill:#ecfdf5,stroke:#059669,stroke-width:1px,color:#111;
    classDef cost fill:#fefce8,stroke:#ca8a04,stroke-width:1px,color:#111;
    classDef future fill:#fef2f2,stroke:#dc2626,stroke-dasharray: 5 5,color:#111;

    DEV[Developer Laptop<br/>Docker Compose / local validation]:::local
    GHA[GitHub Actions<br/>Terraform validation / IaC scanning]:::ci
    JENKINS[Jenkins<br/>future release confidence]:::ci

    TFDEV[Terraform dev environment<br/>infra/environments/dev]:::tf
    TAGS[tags module<br/>common governance metadata]:::aws
    VPC[vpc module<br/>VPC / subnets / route tables / SGs]:::aws
    IAM[iam module<br/>plan policy / guarded trust patterns]:::aws
    ECR[ecr module<br/>API + frontend repositories]:::aws
    BUDGET[budget module<br/>dev cost guardrail]:::cost
    CW[cloudwatch module<br/>short-retention log groups]:::aws

    FUTURE[Future target architecture<br/>EKS / RDS / S3 / DynamoDB / MSK / OpenSearch]:::future

    DEV --> TFDEV
    GHA --> TFDEV
    JENKINS -. future controlled plan/apply .-> TFDEV

    TFDEV --> TAGS
    TFDEV --> VPC
    TFDEV --> IAM
    TFDEV --> ECR
    TFDEV --> BUDGET
    TFDEV --> CW

    TAGS --> VPC
    TAGS --> IAM
    TAGS --> ECR
    TAGS --> BUDGET
    TAGS --> CW

    VPC -. network foundation for .-> FUTURE
    IAM -. future controlled access for .-> FUTURE
    ECR -. future image source for .-> FUTURE
    CW -. future observability for .-> FUTURE
    BUDGET -. cost guardrails before .-> FUTURE
```
