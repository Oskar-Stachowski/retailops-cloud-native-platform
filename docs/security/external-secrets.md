# External Secrets candidate for EKS

These manifests implement the production/EKS pattern for runtime secrets:

- AWS Secrets Manager stores the secret values.
- External Secrets Operator syncs values into the `retailops-runtime-secrets` Kubernetes Secret.
- Application workloads consume the generated Kubernetes Secret through `envFrom`.

Prerequisites:

1. External Secrets Operator installed in the EKS cluster.
2. IRSA configured for the External Secrets service account.
3. AWS Secrets Manager secret named `retailops/dev/runtime` with keys:
   - `DATABASE_URL`
   - `POSTGRES_PASSWORD`

Apply after prerequisites:

```bash
kubectl apply -f k8s/addons/external-secrets/secretstore.aws.yaml
kubectl apply -f k8s/addons/external-secrets/runtime-secrets.externalsecret.yaml
```
