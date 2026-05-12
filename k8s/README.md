# Kubernetes

Kubernetes is the target runtime path for the RetailOps platform.

The current implementation contains only the first base manifests:

- namespace definition for the local-first RetailOps runtime,
- shared application ConfigMap,
- example Secret template with placeholder values only,
- API Deployment and ClusterIP Service,
- frontend Deployment and ClusterIP Service,
- Kustomize base entrypoint.

Ingress, jobs, overlays, Helm charts and EKS deployment automation are not
implemented yet. Current full-stack runtime validation still uses Docker
Compose.

The dev overlay adds an ephemeral PostgreSQL Deployment and ClusterIP Service
for local `kind` or `minikube` validation. It uses placeholder credentials only
and is not a production database pattern. It also includes one-shot Alembic
migration and demo seed Jobs for local validation.

The same dev overlay also runs a single-node Redpanda broker and a one-shot
topic initialization Job for the local real-time event topics. This prepares the
Kubernetes path for a later long-running consumer deployment.

## Layout

```text
k8s/
|-- base/
    |-- api/
    |   |-- deployment.yaml
    |   `-- service.yaml
    |-- config/
    |   |-- app-config.yaml
    |   `-- secret.example.yaml
    |-- frontend/
    |   |-- deployment.yaml
    |   `-- service.yaml
    |-- namespaces/
    |   `-- retailops.yaml
    `-- kustomization.yaml
`-- overlays/
    `-- dev/
        |-- broker/
        |   |-- redpanda-deployment.yaml
        |   |-- redpanda-service.yaml
        |   `-- topic-init-job.yaml
        |-- database/
        |   |-- deployment.yaml
        |   `-- service.yaml
        |-- demo-data/
        |   `-- *.csv
        |-- jobs/
        |   |-- migrate.yaml
        |   `-- seed.yaml
        `-- kustomization.yaml
```

The frontend image currently uses the same Nginx config as Docker Compose. Full
Kubernetes API routing will be validated when ingress or runtime Nginx config is
added in a later commit.

## Validate

Render the base manifests with Kustomize:

```bash
kubectl kustomize k8s/base
```

Render the local dev overlay with PostgreSQL:

```bash
kubectl kustomize k8s/overlays/dev
```

Apply only to a local `kind` or `minikube` cluster until workload manifests and
smoke tests are added:

```bash
kubectl apply -k k8s/overlays/dev
```

The `secret.example.yaml` file documents required secret keys, but it is not
included in the base Kustomize resources. Create real secrets through a local
override or a secret manager integration in later commits.

The dev seed Job mounts demo CSV files from a generated ConfigMap. The overlay
keeps a local copy of the required CSV files so `kubectl kustomize` works with
the default load restrictions and does not require the API image to include
sample data.

## Planned Scope

Future Kubernetes work should include:

- application Deployment and Service manifests,
- environment-specific overlays,
- ingress strategy,
- readiness and liveness probes,
- rollout and rollback strategy,
- resource requests and limits,
- workload identity and secret integration,
- autoscaling policy,
- deployment documentation and smoke tests.

Do not treat this directory as a complete deployment path until those assets
exist and are validated by CI.
