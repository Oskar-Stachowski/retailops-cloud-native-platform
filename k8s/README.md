# Kubernetes

Kubernetes is the target runtime path for the RetailOps platform.

The current implementation contains the first base manifests:

- namespace definition for the local-first RetailOps runtime,
- shared application ConfigMap,
- example Secret template with placeholder values only,
- API Deployment and ClusterIP Service,
- frontend Deployment and ClusterIP Service,
- nginx Ingress manifests for local host-based routing,
- Kustomize base entrypoint.

Helm charts and EKS deployment automation are not implemented yet. Current
full-stack runtime validation still uses Docker Compose.

The dev overlay adds an ephemeral PostgreSQL Deployment and ClusterIP Service
for local `kind` or `minikube` validation. It uses placeholder credentials only
and is not a production database pattern. It also includes one-shot Alembic
migration and demo seed Jobs for local validation.

The same dev overlay also runs a single-node Redpanda broker and a one-shot
topic initialization Job for the local real-time event topics, plus the
long-running real-time consumer Deployment.

Workloads define bounded CPU and memory requests/limits. API and frontend use
HTTP startup, liveness and readiness probes. Dev PostgreSQL and Redpanda use
startup probes plus command-based readiness and liveness checks. The real-time
consumer uses command-based probes because it is a background process without an
HTTP listener.

The API readiness probe targets `/ready`, so Kubernetes removes API Pods from
Service endpoints when PostgreSQL is unavailable. Current resource values are
local dev assumptions sized for `kind` or `minikube`; HPA policy should be added
later against API/frontend CPU or memory metrics after cluster metrics are wired.

The base Ingress assumes an nginx-compatible ingress controller and the local
host `retailops.local`. Frontend traffic is routed from `/` to
`retailops-frontend`; API traffic is routed from `/api/...` to `retailops-api`
with an nginx rewrite so `/api/health` reaches the FastAPI `/health` endpoint.
TLS and AWS ALB-specific annotations are intentionally out of scope for this
local-first manifest set.

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
    |-- ingress/
    |   `-- ingress.yaml
    |-- namespaces/
    |   `-- retailops.yaml
    `-- kustomization.yaml
`-- overlays/
    `-- dev/
        |-- broker/
        |   |-- redpanda-deployment.yaml
        |   |-- redpanda-service.yaml
        |   `-- topic-init-job.yaml
        |-- consumer/
        |   `-- deployment.yaml
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

The frontend image currently uses the same Nginx config as Docker Compose. The
Ingress routes `/api/...` directly to the API service, so local Kubernetes API
traffic does not depend on the frontend container's internal proxy target.

## Validate

Render the base manifests with Kustomize:

```bash
kubectl kustomize k8s/base
```

Render the local dev overlay with PostgreSQL:

```bash
kubectl kustomize k8s/overlays/dev
```

Run the repeatable local Kubernetes smoke test:

```bash
make k8s-smoke
```

The smoke test renders base and dev manifests, parses the rendered YAML, checks
them with `kubeconform`, checks that expected Deployments, Services, Jobs and
Ingresses exist, verifies probe and resource coverage for deployed workloads,
validates the example Secret manifest, and writes a local report under
`ci-cd/reports/k8s/`.

For the full local operating procedure, see
[`docs/runbooks/local-kubernetes-runbook.md`](../docs/runbooks/local-kubernetes-runbook.md).

Apply only to a local `kind` or `minikube` cluster until production-like
overlays, rollout policy and cluster evidence are added:

```bash
kubectl apply -k k8s/overlays/dev
```

For local ingress testing, enable or install an nginx ingress controller and
map `retailops.local` to the cluster ingress address. For many local clusters,
that means adding `127.0.0.1 retailops.local` to `/etc/hosts`.

The `secret.example.yaml` file documents required secret keys, but it is not
included in the base Kustomize resources. Create real secrets through a local
override or a secret manager integration in later commits.

The dev seed Job mounts demo CSV files from a generated ConfigMap. The overlay
keeps a local copy of the required CSV files so `kubectl kustomize` works with
the default load restrictions and does not require the API image to include
sample data.

## Planned Scope

Future Kubernetes work should include:

- environment-specific overlays,
- rollout and rollback strategy,
- workload identity and secret integration,
- autoscaling policy,
- deployment documentation and smoke tests.

Do not treat this directory as a complete deployment path until those assets
exist and are validated by CI.
