# RetailOps Falco runtime threat detection

This folder implements runtime detection rules for the RetailOps Kubernetes namespace.

## Rules

```text
security/falco/rules/retailops_runtime_rules.yaml
```

Implemented detections:

- shell spawned inside a RetailOps container;
- sensitive file reads;
- package-manager execution at runtime.

## Local validation

```bash
falco --validate security/falco/rules/retailops_runtime_rules.yaml
```

## Runtime demo

After Falco is installed in the cluster:

```bash
kubectl -n retailops exec deploy/retailops-api -- sh -c 'id'
kubectl -n falco logs deploy/falco --tail=100 | grep RetailOps
```

Archive the output under:

```text
ci-cd/reports/runtime/falco-retailops-alerts.txt
```
