# Local Kubernetes Runbook

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** Kubernetes / Local Operations / Deployment Validation  
**Sprint:** Sprint 13 — Kubernetes Runtime Foundation  
**Commit:** `docs: add local Kubernetes runbook`

---

## 1. Purpose

This runbook explains how to validate and run the RetailOps Kubernetes manifests
on a local Kubernetes cluster such as `kind` or `minikube`.

Use it when:

- Kubernetes manifests changed,
- a reviewer asks how to run the local K8s path,
- `make k8s-smoke` fails,
- a local `kind` or `minikube` deployment needs to be validated,
- ingress, probes, jobs or the realtime consumer need troubleshooting.

Local Kubernetes rule:

> Validate manifests first. Apply to a local cluster only after render checks
> are green.

Current runtime scope:

```text
nginx ingress -> frontend service -> frontend Deployment
              -> /api rewrite -> API service -> API Deployment
API / consumer -> PostgreSQL dev Deployment
consumer       -> Redpanda dev Deployment
jobs           -> migrations, seed data, topic init
```

---

## 2. Prerequisites

Required for manifest validation:

```bash
kubectl version --client
ruby --version
make --version
```

Required for local cluster deployment:

```bash
docker version
kind version
# or:
minikube version
```

Required local images:

```text
retailops-api:0.1.0
retailops-frontend:0.1.0
```

Build them locally before applying manifests:

```bash
docker build -t retailops-api:0.1.0 services/api
docker build -t retailops-frontend:0.1.0 frontend
```

The dev overlay creates placeholder local secrets with `change-me` values. Do
not reuse this overlay as a production database or secret pattern.

---

## 3. Fast Validation Without a Cluster

Run the Kubernetes smoke test:

```bash
make k8s-smoke
```

The smoke test:

- renders `k8s/base`,
- renders `k8s/overlays/dev`,
- parses rendered YAML,
- checks required Deployments, Services, Jobs and Ingresses,
- checks probe and resource coverage for deployed workloads,
- writes a local report to `ci-cd/reports/k8s/kubernetes-smoke.txt`.

The report is ignored by Git by default because it is local and regenerated.

If this fails, inspect the report:

```bash
cat ci-cd/reports/k8s/kubernetes-smoke.txt
```

You can also run the underlying render commands directly:

```bash
kubectl kustomize k8s/base
kubectl kustomize k8s/overlays/dev
```

---

## 4. Optional Server-Side Dry Run

Use a server-side dry run only when a local cluster is already available:

```bash
K8S_SMOKE_DRY_RUN=1 make k8s-smoke
```

This adds:

```bash
kubectl apply --dry-run=server
```

Use this after local API server availability is confirmed:

```bash
kubectl cluster-info
```

---

## 5. Create a Local kind Cluster

Create a cluster:

```bash
kind create cluster --name retailops
```

Load local images into the cluster:

```bash
kind load docker-image retailops-api:0.1.0 --name retailops
kind load docker-image retailops-frontend:0.1.0 --name retailops
```

Confirm access:

```bash
kubectl cluster-info --context kind-retailops
kubectl get nodes
```

If using `minikube`, build images inside the minikube Docker environment or load
them with the equivalent minikube image command:

```bash
minikube image load retailops-api:0.1.0
minikube image load retailops-frontend:0.1.0
```

---

## 6. Apply the Dev Overlay

Apply the local dev overlay:

```bash
kubectl apply -k k8s/overlays/dev
```

Watch the namespace:

```bash
kubectl get all -n retailops
```

Expected workload types:

```text
Deployment/retailops-api
Deployment/retailops-frontend
Deployment/postgres
Deployment/redpanda
Deployment/retailops-realtime-consumer
Job/retailops-migrate
Job/retailops-seed-demo-data
Job/redpanda-topic-init
```

Wait for Deployments:

```bash
kubectl rollout status deployment/postgres -n retailops
kubectl rollout status deployment/redpanda -n retailops
kubectl rollout status deployment/retailops-api -n retailops
kubectl rollout status deployment/retailops-frontend -n retailops
kubectl rollout status deployment/retailops-realtime-consumer -n retailops
```

Check Jobs:

```bash
kubectl get jobs -n retailops
kubectl logs job/retailops-migrate -n retailops
kubectl logs job/retailops-seed-demo-data -n retailops
kubectl logs job/redpanda-topic-init -n retailops
```

---

## 7. Local Service Validation

Port-forward the API:

```bash
kubectl port-forward -n retailops service/retailops-api 8000:8000
```

Check health and readiness from another terminal:

```bash
curl --silent --show-error http://localhost:8000/health
curl --silent --show-error http://localhost:8000/ready
```

Port-forward the frontend:

```bash
kubectl port-forward -n retailops service/retailops-frontend 3000:80
```

Check the frontend:

```bash
curl --silent --show-error --head http://localhost:3000/
```

Check live operations:

```bash
curl --silent --show-error \
  "http://localhost:8000/dashboard/live-operations?window_minutes=15"
```

---

## 8. Local Ingress Validation

The base Ingress assumes:

```text
ingressClassName: nginx
host: retailops.local
```

Install or enable an nginx ingress controller for the local cluster before using
Ingress. For `minikube`:

```bash
minikube addons enable ingress
```

For `kind`, install an nginx ingress controller compatible with kind, then wait
for the controller Pod to be ready in its namespace.

Map `retailops.local` to the ingress address. For many local setups:

```text
127.0.0.1 retailops.local
```

Then test:

```bash
curl --silent --show-error http://retailops.local/
curl --silent --show-error http://retailops.local/api/health
curl --silent --show-error http://retailops.local/api/ready
```

Expected routing:

| Request | Backend |
|---|---|
| `/` | `retailops-frontend` |
| `/api/health` | `retailops-api` as `/health` |
| `/api/ready` | `retailops-api` as `/ready` |

TLS and AWS ALB annotations are intentionally out of scope for this local
manifest set.

---

## 9. Realtime Consumer Checks

Check the consumer Pod:

```bash
kubectl get pods -n retailops -l app.kubernetes.io/name=retailops-realtime-consumer
kubectl logs -n retailops deployment/retailops-realtime-consumer
```

Check Redpanda topics:

```bash
kubectl exec -n retailops deployment/redpanda -- \
  rpk -X brokers=redpanda:9092 topic list
```

Expected topics:

```text
retailops.sales.v1
retailops.inventory.v1
retailops.pricing.v1
retailops.intelligence.v1
retailops.operations.v1
retailops.dlq.v1
```

---

## 10. Troubleshooting

### ImagePullBackOff

The local cluster cannot see images from the host Docker daemon.

For kind:

```bash
kind load docker-image retailops-api:0.1.0 --name retailops
kind load docker-image retailops-frontend:0.1.0 --name retailops
```

For minikube:

```bash
minikube image load retailops-api:0.1.0
minikube image load retailops-frontend:0.1.0
```

Then restart the affected Deployment:

```bash
kubectl rollout restart deployment/retailops-api -n retailops
kubectl rollout restart deployment/retailops-frontend -n retailops
```

### API readiness fails

The API readiness probe depends on PostgreSQL.

Check database status:

```bash
kubectl get pods -n retailops -l app.kubernetes.io/name=postgres
kubectl logs -n retailops deployment/postgres
kubectl describe pod -n retailops -l app.kubernetes.io/name=retailops-api
```

Check migrations:

```bash
kubectl get job retailops-migrate -n retailops
kubectl logs job/retailops-migrate -n retailops
```

### Seed job fails

Check whether migrations completed first:

```bash
kubectl get jobs -n retailops
kubectl logs job/retailops-migrate -n retailops
kubectl logs job/retailops-seed-demo-data -n retailops
```

### Consumer waits forever

The consumer waits for migrations and Redpanda topics before it starts.

Check:

```bash
kubectl logs -n retailops deployment/retailops-realtime-consumer -c wait-for-migrations
kubectl logs -n retailops deployment/retailops-realtime-consumer -c wait-for-redpanda-topics
kubectl logs job/redpanda-topic-init -n retailops
```

### Ingress returns 404

Check ingress resources:

```bash
kubectl get ingress -n retailops
kubectl describe ingress retailops-api -n retailops
kubectl describe ingress retailops-frontend -n retailops
```

Confirm the request uses the expected host:

```bash
curl --header "Host: retailops.local" http://127.0.0.1/api/health
```

---

## 11. Cleanup

Delete RetailOps resources:

```bash
kubectl delete -k k8s/overlays/dev
```

Delete the local kind cluster:

```bash
kind delete cluster --name retailops
```

For minikube:

```bash
minikube delete
```

---

## 12. Evidence Notes

For local evidence, capture command output from:

```bash
make k8s-smoke
kubectl get all -n retailops
kubectl get ingress -n retailops
kubectl logs job/retailops-migrate -n retailops
kubectl logs job/retailops-seed-demo-data -n retailops
```

Store raw local reports under:

```text
ci-cd/reports/k8s/
```

Before committing evidence, sanitize local paths, private hostnames, cluster
names, tokens and any environment-specific values. Prefer short `*-snapshot.txt`
files or curated notes over full raw logs.
