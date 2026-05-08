# EKS Bootstrap Strategy and Cost Guardrails

**Project:** Cloud-Native RetailOps Platform  
**Sprint:** 13 — Kubernetes / EKS Foundation  
**Commit:** 13.1 — `docs: define EKS provisioning strategy and cost guardrails`  
**Status:** Accepted strategy for Sprint 13 planning  
**Implementation level:** Documentation and decision record only. This commit must not create AWS resources.

---

## 1. Purpose

This document defines how RetailOps should approach Amazon EKS provisioning during Sprint 13.

The goal is to introduce EKS in a cost-aware and production-minded way without accidentally turning a portfolio project into an always-on cloud environment.

This document answers four practical questions:

1. When do we use a real AWS EKS cluster?
2. When do we use a local Kubernetes fallback such as `kind`?
3. When is Terraform allowed to run `apply` and when should it remain `plan` only?
4. What cleanup, tagging, and risk controls are required before any EKS experiment?

---

## 2. Decision summary

RetailOps will use a **local-first Kubernetes workflow** by default and introduce real AWS EKS only for short, intentional validation windows.

| Decision area | Accepted decision |
|---|---|
| Default Kubernetes runtime during early Sprint 13 | Local `kind` or equivalent local Kubernetes runtime. |
| Default Terraform behavior | `terraform fmt`, `terraform validate`, security checks, and `terraform plan` only. |
| EKS `apply` policy | Allowed only for a short-lived `dev` validation environment after explicit approval. |
| Long-running EKS cluster | Not allowed during the current sprint unless a later task explicitly changes the policy. |
| Production-like EKS | Documented as target maturity, not required for this commit. |
| Cost posture | Keep AWS cost near zero unless running a planned EKS validation window. |
| Cleanup posture | Destroy EKS resources immediately after evidence is captured. |
| Evidence posture | Every real EKS run must produce plan, validation, access, workload, and cleanup evidence. |

---

## 3. Why this decision fits RetailOps

RetailOps is a production-oriented DevOps portfolio project, but it is still being built in controlled stages.

EKS is justified in the target architecture because the platform is expected to run multiple workload types:

- FastAPI backend services,
- frontend web application,
- asynchronous workers,
- future event consumers,
- future scheduled jobs,
- future ML inference services,
- observability and platform components.

However, not every Kubernetes learning or manifest validation task requires a paid AWS cluster. Local Kubernetes is enough for most early workload design work. Real EKS becomes useful when we need to validate AWS-specific integration points such as IAM, IRSA, ECR image pulling, AWS Load Balancer Controller assumptions, cluster access, managed node groups, and Terraform-managed cluster lifecycle.

This decision keeps the project credible for DevOps recruiters because it demonstrates both ambition and operational discipline: Kubernetes is introduced, but cloud cost and cleanup risk are controlled from the beginning.

---

## 4. Bootstrap modes

### 4.1. Mode A — Documentation and plan-only mode

**Purpose:** design and review infrastructure before creating anything in AWS.

Use this mode for:

- EKS module skeleton work,
- Terraform input/output design,
- cluster naming and tagging decisions,
- node group design,
- IAM/OIDC design,
- security review,
- cost review,
- CI checks.

Allowed commands:

```bash
terraform fmt -recursive
terraform validate
terraform plan
```

Not allowed:

```bash
terraform apply
terraform destroy
```

`destroy` is not needed when nothing has been created.

---

### 4.2. Mode B — Local Kubernetes fallback with `kind`

**Purpose:** validate Kubernetes manifests and developer workflow with zero AWS runtime cost.

Use this mode for:

- namespace strategy,
- basic Deployments, Services, ConfigMaps, and Secrets placeholders,
- probes and resource requests,
- local workload smoke tests,
- frontend/API local runtime validation,
- early platform learning.

Recommended local validation path:

```bash
kind create cluster --name retailops-dev
kubectl cluster-info --context kind-retailops-dev
kubectl apply -f k8s/namespaces/
kubectl get namespaces
kind delete cluster --name retailops-dev
```

Local Kubernetes does not prove AWS-specific behavior, but it is the safest default before touching EKS.

---

### 4.3. Mode C — Short-lived AWS EKS validation

**Purpose:** prove that the Terraform/EKS foundation can create a real cluster and that basic platform operations work against AWS-managed Kubernetes.

Use this mode only when all preconditions in this document are met.

A real EKS run should validate only the minimum required platform assumptions:

- cluster can be created,
- node group can join the cluster,
- `kubectl` access can be configured,
- namespaces can be created,
- basic workload can be scheduled,
- tags are visible,
- cost and cleanup controls are followed,
- cluster can be destroyed cleanly.

This mode is not intended to host a persistent RetailOps environment.

---

### 4.4. Mode D — Target production-like EKS maturity

**Purpose:** document the long-term architecture direction.

This mode may include:

- private worker nodes,
- multiple node groups,
- autoscaling,
- ingress controller,
- external DNS,
- cert-manager,
- secrets integration,
- CloudWatch or OpenTelemetry integration,
- policy-as-code,
- multi-environment promotion.

This mode is out of scope for Commit 13.1.

---

## 5. Decision matrix: local `kind` vs real AWS EKS

| Question | Use local `kind` | Use real AWS EKS |
|---|---:|---:|
| Am I only validating YAML syntax and object relationships? | Yes | No |
| Am I learning namespace, Deployment, Service, and probe basics? | Yes | No |
| Am I testing local API/frontend containers? | Yes | No |
| Am I validating Terraform module design without resources? | No, use Terraform plan | No apply |
| Am I validating managed node group behavior? | No | Yes |
| Am I validating IRSA/OIDC behavior? | No | Yes |
| Am I validating ECR image pulling from AWS? | No | Yes |
| Am I validating AWS Load Balancer Controller assumptions? | No | Yes, later |
| Am I collecting portfolio evidence that a real cluster can be recreated? | No | Yes |
| Do I need the cluster running for more than a few hours? | Prefer local | Not allowed by default |
| Do I have no cleanup time today? | Yes | No |

Senior DevOps rule: use the cheapest environment that can answer the engineering question.

---

## 6. Terraform apply policy

### 6.1. Default policy: plan only

Until Sprint 13 reaches a dedicated EKS validation task, Terraform must remain in plan-only mode for EKS resources.

Allowed by default:

```bash
cd infra/environments/dev
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform show -no-color tfplan > ../../../ci-cd/reports/iac/terraform-plan-eks.txt
```

Blocked by default:

```bash
terraform apply
terraform apply -auto-approve
```

### 6.2. Apply can be allowed only when all conditions are true

A real EKS apply may be performed only if:

- the task explicitly requires real AWS validation,
- the expected cost has been reviewed,
- AWS budget/alerting is already configured,
- the cluster lifetime window is defined before creation,
- cleanup time is reserved in the same working session,
- the AWS account and region are intentionally selected,
- Terraform plan has been reviewed,
- security/IaC checks have passed or exceptions are documented,
- no secrets or account identifiers will be committed,
- evidence destination is prepared,
- rollback and destroy commands are known before apply.

### 6.3. No unattended apply

Do not run EKS apply before leaving the computer, before sleep, or when there is no time to destroy resources.

EKS experiments should be treated like a controlled maintenance window:

```text
plan → apply → validate → capture evidence → destroy → verify cleanup
```

---

## 7. EKS validation window policy

For portfolio validation, use a short-lived window.

| Control | Sprint 13 default |
|---|---|
| Environment | `dev` only |
| Cluster lifetime | 2–3 hours target, same-day cleanup required |
| Number of clusters | 1 maximum |
| Node groups | 1 small managed node group initially |
| Desired nodes | 1 by default, 2 only if required |
| Maximum nodes | 2 by default |
| NAT Gateway | Avoid by default for early validation |
| Load balancer | Avoid unless the task specifically validates ingress |
| RDS/MSK/OpenSearch | Not part of EKS bootstrap validation |
| Production data | Not allowed |
| Real secrets | Not allowed |
| Cleanup evidence | Required |

---

## 8. Bootstrap sequence

### 8.1. Day 0 — Design and dry run

Before any AWS apply:

1. Review this document.
2. Review `docs/eks-sizing-cost-review.md`.
3. Confirm the branch is dedicated to Sprint 13 work.
4. Confirm no real secrets are present in the repository.
5. Run Terraform formatting and validation.
6. Run Terraform plan.
7. Save plan output as evidence.
8. Review estimated cost and cleanup policy.

Expected output:

```text
terraform fmt: clean
terraform validate: success
terraform plan: reviewed, no apply yet
```

### 8.2. Day 1 — Optional short-lived EKS creation

Only after explicit approval:

1. Export/select the intended AWS profile and region.
2. Confirm budget/alerts are active.
3. Run `terraform plan` again.
4. Run `terraform apply` manually.
5. Configure `kubectl` access.
6. Verify cluster and nodes.
7. Create or verify namespaces.
8. Optionally schedule a minimal test workload.
9. Capture evidence.
10. Destroy resources.
11. Verify cleanup.

### 8.3. Day 2 — Post-run review

After the cluster is destroyed:

1. Review actual resources created.
2. Review whether any resources survived cleanup.
3. Update evidence notes.
4. Document any manual cleanup.
5. Decide whether the next commit should refine Terraform, IAM, namespaces, or runbooks.

---

## 9. Tagging policy

All AWS resources created for EKS must use the shared RetailOps tagging strategy.

Required tags:

| Tag | Example value | Purpose |
|---|---|---|
| `Project` | `RetailOps` | Groups all project resources. |
| `Environment` | `dev` | Separates dev/staging/prod-like costs. |
| `Owner` | `oskar` | Identifies the responsible person. |
| `ManagedBy` | `terraform` | Shows provisioning source. |
| `CostCenter` | `portfolio` | Supports cost grouping. |
| `Lifecycle` | `temporary` | Signals cleanup requirement. |
| `Component` | `eks` | Identifies EKS-related resources. |
| `Sprint` | `13` | Helps portfolio evidence and cleanup. |

Recommended additional tags:

| Tag | Example value | Purpose |
|---|---|---|
| `DeleteAfter` | `2026-05-08` | Clear cleanup intent for temporary resources. |
| `Workload` | `platform` | Groups platform workloads. |
| `IaCPath` | `infra/environments/dev` | Helps trace resource origin. |

Do not put secrets, account IDs, personal contact details, or private data in tags.

---

## 10. Cleanup policy

Cleanup is part of the EKS task, not an optional afterthought.

### 10.1. Cleanup rule

Every real EKS apply must end with one of these outcomes:

| Outcome | Acceptable? | Notes |
|---|---:|---|
| Cluster destroyed and cleanup evidence saved | Yes | Preferred outcome. |
| Cluster intentionally kept temporarily with written reason and deletion time | Rarely | Must be explicitly documented. |
| Cluster left running without reason | No | Treat as process failure. |
| Terraform state lost before destroy | No | Requires manual cleanup and incident note. |

### 10.2. Standard destroy flow

```bash
cd infra/environments/dev
terraform plan -destroy
terraform destroy
```

After destroy, verify through AWS Console or CLI that no expensive resources remain.

### 10.3. Cleanup verification checklist

Verify these resource classes after EKS cleanup:

- EKS clusters,
- EKS node groups,
- EC2 instances,
- Auto Scaling Groups,
- Launch Templates,
- Load Balancers,
- Target Groups,
- NAT Gateways,
- Elastic IPs,
- unattached EBS volumes,
- security groups created for the cluster,
- CloudWatch log groups with unexpected retention,
- IAM roles created only for the temporary cluster,
- ECR images if the validation pushed temporary images.

### 10.4. Cleanup evidence

Save cleanup evidence under the later Sprint 13 evidence path:

```text
docs/evidence/eks/
```

Recommended evidence files for later commits:

```text
docs/evidence/eks/terraform-plan-eks.txt
docs/evidence/eks/terraform-apply-eks.txt
docs/evidence/eks/terraform-destroy-eks.txt
docs/evidence/eks/cluster-recreation-checklist.md
```

Commit 13.1 defines the policy. It does not need to create live cleanup evidence yet.

---

## 11. Risk register

| Risk | Why it matters | Guardrail |
|---|---|---|
| EKS left running overnight | Creates unnecessary control plane and node cost. | Short validation window, same-day destroy, cleanup checklist. |
| NAT Gateway left running | Can create cost even without useful workload traffic. | Avoid NAT by default in early validation; verify after destroy. |
| Load Balancer created by ingress/service | Can survive or add cost if not cleaned correctly. | Avoid ingress in early validation; verify ELB resources after destroy. |
| CloudWatch logs retained unexpectedly | Long retention increases cost and clutter. | Use short retention for temporary validation. |
| Terraform state mismatch | Destroy may miss resources or become risky. | Keep state controlled, do not manually mutate resources unless documenting cleanup. |
| IAM permissions too broad | Weakens security story and review quality. | Prefer least privilege and separate EKS admin/bootstrap from workload IRSA. |
| Local `kind` success mistaken for EKS success | Local Kubernetes does not prove AWS integrations. | Use decision matrix and mark evidence type clearly. |
| Overengineering too early | Slows delivery and increases cost. | Validate minimum EKS foundation before adding ingress, autoscaling, or controllers. |
| Production-like claims without evidence | Reduces portfolio credibility. | Clearly separate implemented evidence from target maturity. |

---

## 12. Security guardrails

Before any EKS apply:

- do not commit kubeconfig files,
- do not commit AWS credentials,
- do not commit Terraform state files,
- do not expose account IDs in screenshots unless intentionally redacted,
- prefer IAM roles over long-lived users,
- prepare IRSA/OIDC foundation before workload-specific AWS permissions,
- keep demo workloads free of production data,
- keep namespace separation clear from the beginning.

Suggested `.gitignore` protection should already cover local Terraform state and environment files. If new kubeconfig or generated files appear during Sprint 13, they must be reviewed before commit.

---

## 13. Observability and validation guardrails

A real EKS cluster is not considered useful evidence unless basic operational checks are captured.

Minimum checks for a later real EKS run:

```bash
kubectl get nodes
kubectl get namespaces
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
```

Minimum application checks after workload deployment:

```bash
kubectl get deployment -n retailops-app
kubectl get service -n retailops-app
kubectl describe pod -n retailops-app <pod-name>
```

Do not confuse “cluster exists” with “platform is operable.” The evidence should show that access, nodes, namespaces, and at least one workload path can be validated.

---

## 14. Definition of Done for Commit 13.1

Commit 13.1 is complete when:

- EKS provisioning strategy is documented,
- local `kind` fallback is documented,
- plan-only versus apply policy is documented,
- short-lived EKS validation policy is documented,
- cleanup policy is documented,
- required tags are documented,
- risks and guardrails are documented,
- cost review is documented in `docs/eks-sizing-cost-review.md`,
- no AWS resources are created by this commit.

---

## 15. Next commits enabled by this document

| Next commit | How this document helps |
|---|---|
| 13.2 — EKS module skeleton | Provides inputs, naming, tags, and no-apply posture. |
| 13.3 — EKS node group module | Defines initial node group sizing and cost constraints. |
| 13.4 — IAM OIDC foundation | Explains why IRSA/OIDC belongs before workload AWS permissions. |
| 13.5 — connect modules into dev | Defines when dev should remain plan-only. |
| 13.6 — namespace strategy | Separates local `kind` validation from EKS validation. |
| 13.7 — kubectl access and bootstrap runbook | Provides the bootstrap sequence and validation expectations. |
| 13.8 — evidence checklist | Provides cleanup and validation evidence requirements. |

