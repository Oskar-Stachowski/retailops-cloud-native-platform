# RetailOps Kubernetes policy-as-code

This folder implements Kubernetes policy-as-code for local validation and admission-control candidates.

| Folder | Purpose |
|---|---|
| `policy/conftest` | CI/local policy gate for Kubernetes YAML and Kustomize config |
| `policy/kyverno` | Runtime admission policy candidates for EKS clusters using Kyverno |
| `policy/gatekeeper` | Runtime admission policy candidates for OPA Gatekeeper |

## Local validation

```bash
docker run --rm \
  -v "$PWD:/project" \
  -w /project \
  openpolicyagent/conftest:v0.56.0 \
  test k8s/base k8s/overlays/dev --policy policy/conftest
```

## Evidence

Policy reports should be stored under:

```text
ci-cd/reports/k8s/
ci-cd/reports/policy/
```
