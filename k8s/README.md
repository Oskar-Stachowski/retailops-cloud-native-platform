# Kubernetes

Kubernetes is future deployment scope for the RetailOps platform.

There are no implemented Kubernetes manifests, Helm charts, Kustomize overlays, controllers, or EKS deployment automation in this directory yet. Current application runtime validation uses Docker Compose, and current AWS infrastructure work is limited to the Terraform foundation under `infra/`.

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

Do not treat this directory as an implemented deployment path until those assets exist and are validated by CI.
