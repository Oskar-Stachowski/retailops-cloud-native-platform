# Kubernetes

RetailOps has base application manifests and a local dev overlay, plus a
repeatable kind runtime drill. EKS deployment and Helm charts remain future work.

- `base/`: namespace, ConfigMap, service accounts, API/frontend Deployments and
  Services, Traefik Ingress and default-deny/internal/DNS/ingress NetworkPolicies.
- `overlays/dev/`: PostgreSQL and Redpanda with separate PVCs, migration/seed/topic
  Jobs, demo fixtures, and the realtime consumer.
- `scripts/kubernetes/`: isolated runtime drill, infrastructure manifests and checks.

```bash
make k8s-ci                 # Kustomize, schemas, Conftest, Checkov
make k8s-runtime-drill      # real kind deployment, failure/restart/update/rollback
```

The runtime drill generates its own credentials, builds committed versions for
the native node architecture and cleans up its own cluster and image tags.
Published GHCR v0.2.1 is AMD64; native ARM64 drill builds are separate artifacts.
Read the [local runbook](../docs/runbooks/local-kubernetes-runbook.md) for
prerequisites, checks, image identity, evidence, limits and cleanup.

The base host is `retailops.local`. Traefik forwards to the frontend; its Nginx
proxies `/api/` through the `api` Service alias to the same Pods as `retailops-api`.
The ingress-controller policy permits the `traefik` namespace to access frontend
port 8080. kind's default CNI is replaced by digest-pinned kindnet v1.0.1 in the
drill so NetworkPolicy enforcement can be tested, rather than merely rendered.

The dev PVCs require a default StorageClass and survive Pod replacement. They do
not survive destruction of a kind cluster. PostgreSQL and Redpanda are single
replica, `Recreate` workloads; this is development persistence, not HA storage.

For manual deployment, copy `overlays/dev/secrets/runtime-secrets.env.example`
to the ignored local `runtime-secrets.env`, supply disposable local credentials,
provide the application images and a compatible ingress controller/storage/CNI,
then apply the overlay to an explicitly selected local cluster. The drill is the
supported automated validation path and does not read that local secret file.
Never use this dev overlay as a production database or secret pattern.
