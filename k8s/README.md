# Kubernetes

Kubernetes is the target runtime path for the RetailOps platform.

The current implementation contains only the first base manifests:

- namespace definition for the local-first RetailOps runtime,
- shared application ConfigMap,
- example Secret template with placeholder values only,
- Kustomize base entrypoint.

Application Deployments, Services, ingress, jobs, probes, resource limits,
overlays, Helm charts and EKS deployment automation are not implemented yet.
Current full-stack runtime validation still uses Docker Compose.

## Layout

```text
k8s/
`-- base/
    |-- config/
    |   |-- app-config.yaml
    |   `-- secret.example.yaml
    |-- namespaces/
    |   `-- retailops.yaml
    `-- kustomization.yaml
```

## Validate

Render the base manifests with Kustomize:

```bash
kubectl kustomize k8s/base
```

Apply only to a local `kind` or `minikube` cluster until workload manifests and
smoke tests are added:

```bash
kubectl apply -k k8s/base
```

The `secret.example.yaml` file documents required secret keys, but it is not
included in the base Kustomize resources. Create real secrets through a local
override or a secret manager integration in later commits.

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
