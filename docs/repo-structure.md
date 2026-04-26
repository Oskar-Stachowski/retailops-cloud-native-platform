# Repository Structure

```text
retailops-cloud-native-ai-platform/
│
├── README.md
├── case-study.md
├── LICENSE
├── .gitignore
├── .env.example
├── Makefile
├── docker-compose.yml
│
├── docs/
│   ├── architecture/
│   │   ├── aws-architecture.md
│   │   ├── kubernetes-architecture.md
│   │   ├── microservices.md
│   │   ├── data-flow.md
│   │   └── security-governance.md
│   │
│   ├── technical/
│   │   ├── aws-services-inventory.md
│   │   ├── terraform-modules.md
│   │   ├── ci-cd-pipeline.md
│   │   ├── observability.md
│   │   └── mlops-lifecycle.md
│   │
│   ├── business/
│   │   ├── business-objectives.md
│   │   ├── kpis.md
│   │   ├── challenges-tradeoffs.md
│   │   └── future-improvements.md
│   │
│   └── GPTimages/
│       ├── Business-Product-Perspective.png
│       ├── AWS-Cloud-Architecture.png
│       ├── Architecture-Layers.png
│       ├── CI-CD-Pipeline-Delivery-Workflow.png
│       └── ...
│
├── services/
│   ├── api-gateway/
│   ├── inventory-service/
│   ├── sales-service/
│   ├── forecasting-service/
│   ├── anomaly-detection-service/
│   ├── recommendation-service/
│   ├── data-access-service/
│   └── notification-service/
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── ml/
│   ├── notebooks/
│   ├── training/
│   ├── inference/
│   ├── models/
│   ├── experiments/
│   └── README.md
│
├── data/
│   ├── sample/
│   ├── schemas/
│   └── seed/
│
├── infra/
│   ├── terraform/
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   ├── modules/
│   │   │   ├── vpc/
│   │   │   ├── eks/
│   │   │   ├── ecr/
│   │   │   ├── rds/
│   │   │   ├── s3/
│   │   │   ├── iam/
│   │   │   └── monitoring/
│   │   └── README.md
│   │
│   └── aws/
│       ├── policies/
│       ├── iam/
│       └── diagrams/
│
├── k8s/
│   ├── base/
│   ├── overlays/
│   │   ├── dev/
│   │   ├── staging/
│   │   └── prod/
│   ├── helm/
│   └── README.md
│
├── observability/
│   ├── prometheus/
│   ├── grafana/
│   ├── alertmanager/
│   ├── opensearch/
│   └── dashboards/
│
├── security/
│   ├── trivy/
│   ├── snyk/
│   ├── sonarqube/
│   ├── falco/
│   ├── policies/
│   └── README.md
│
├── ci-cd/
│   ├── jenkins/
│   │   ├── Jenkinsfile
│   │   └── pipelines/
│   └── github-actions/
│       ├── ci.yml
│       ├── security-scan.yml
│       └── terraform-check.yml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── load/
│
└── scripts/
    ├── setup-local.sh
    ├── run-tests.sh
    ├── build-images.sh
    └── deploy-local.sh
```