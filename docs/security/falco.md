# RetailOps Falco runtime threat detection

`security/falco/` contains rule candidates for the RetailOps Kubernetes namespace.
The repository does not install or prove a running Falco detector; the commands
below are a manual validation path after installation.

## Rules

```text
security/falco/rules/retailops_runtime_rules.yaml
```

Rule definitions:

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
