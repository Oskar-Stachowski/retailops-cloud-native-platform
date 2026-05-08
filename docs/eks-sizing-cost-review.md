# EKS Sizing and Cost Review

**Project:** Cloud-Native RetailOps Platform  
**Sprint:** 13 — Kubernetes / EKS Foundation  
**Commit:** 13.1 — `docs: define EKS provisioning strategy and cost guardrails`  
**Status:** Accepted cost guardrail for early EKS work  
**Implementation level:** Planning and guardrails only. This document does not authorize always-on EKS.

---

## 1. Purpose

This document defines the first sizing and cost guardrails for introducing Amazon EKS into RetailOps.

The goal is not to produce a final production cost model. The goal is to prevent accidental spend while still allowing a short, controlled EKS validation when it becomes useful for portfolio evidence.

This document should be read together with:

- `docs/eks-bootstrap.md`,
- `docs/finops.md`,
- `docs/cost-assumptions.md`,
- `docs/tagging-strategy.md`,
- `docs/runbooks/aws-cleanup-runbook.md`,
- `infra/environments/dev/`,
- `infra/modules/`,
- `k8s/README.md`.

---

## 2. Pricing source policy

Cloud prices change and vary by region. Before any real EKS apply, verify prices using the official AWS pricing pages and, ideally, AWS Pricing Calculator.

Current planning assumptions:

| Cost item | Planning assumption | Notes |
|---|---|---|
| EKS cluster standard support | `0.10 USD per cluster-hour` | Control plane charge while the cluster exists. |
| EKS cluster extended support | `0.60 USD per cluster-hour` | Avoid for this project; use a standard-supported Kubernetes version. |
| Worker nodes | Charged separately | EC2, EBS, public IPv4, and data transfer are separate from the EKS cluster fee. |
| NAT Gateway | Hourly and data processing charges | Avoid by default in early validation because it can become an idle-cost trap. |
| Load Balancer | Charged separately if created | Avoid ingress/load balancer validation until needed. |
| CloudWatch logs | Charged by ingestion/storage | Keep retention short for temporary clusters. |

Source links for manual verification:

- Amazon EKS pricing: <https://aws.amazon.com/eks/pricing/>
- Amazon VPC pricing, including NAT Gateway pricing: <https://aws.amazon.com/vpc/pricing/>
- AWS Pricing Calculator: <https://calculator.aws/>

---

## 3. Cost posture

RetailOps uses this cost posture for Sprint 13:

```text
Design locally → validate with Terraform plan → use kind for Kubernetes basics → create EKS only for short evidence windows → destroy immediately.
```

The project should not keep EKS running just to “have Kubernetes.”

EKS should answer a specific question:

- Can Terraform create the cluster?
- Can the node group join?
- Can `kubectl` access work?
- Can namespaces be applied?
- Can the workload schedule?
- Can IAM/OIDC support future IRSA?
- Can the whole environment be destroyed and recreated?

If the task does not require one of those questions, use local Kubernetes or plan-only validation instead.

---

## 4. EKS sizing principles

### 4.1. Senior DevOps sizing rule

Start with the smallest environment that can prove the current platform assumption.

Do not size the cluster for a future enterprise architecture before the project has:

- stable Kubernetes manifests,
- working image build and registry workflow,
- namespace strategy,
- clear workload resource requests,
- cleanup runbook,
- cost evidence,
- observability baseline.

### 4.2. Workloads considered for early validation

Early EKS validation may include only lightweight platform workloads.

| Workload | Early EKS requirement | Notes |
|---|---:|---|
| API | Optional | Useful only after image build/push path exists. |
| Frontend | Optional | Useful only after ECR or public image strategy exists. |
| PostgreSQL | No | Use managed database later or local/CI DB for early work. Do not run stateful DB on early EKS unless specifically testing Kubernetes storage. |
| Observability stack | No by default | Local Prometheus/Grafana already exists; avoid cluster cost increase early. |
| Workers/consumers | Later | Add after basic API/frontend deployment model is stable. |
| ML inference | Later | Belongs to future maturity, not initial EKS bootstrap. |

### 4.3. Initial resource request assumptions

These values are planning assumptions for future Kubernetes manifests, not hard commitments.

| Component | CPU request | Memory request | Reasoning |
|---|---:|---:|---|
| Frontend | `50m–100m` | `64Mi–128Mi` | Static nginx-served frontend should be lightweight. |
| API | `100m–250m` | `256Mi–512Mi` | FastAPI app with moderate local/demo traffic. |
| Worker | `100m–250m` | `256Mi–512Mi` | Future async workload placeholder. |
| Metrics sidecar/agent | Avoid initially | Avoid initially | Do not add cluster observability agents before basic workload validation. |

Resource requests should be refined after actual Kubernetes manifests and metrics exist.

---

## 5. Recommended early EKS shape

### 5.1. Default Sprint 13 validation cluster

| Area | Default value |
|---|---|
| Environment | `dev` |
| Cluster count | 1 |
| Cluster lifetime | 2–3 hours target, same-day cleanup required |
| Kubernetes version | Standard-supported EKS version only |
| Node group count | 1 |
| Desired nodes | 1 |
| Maximum nodes | 2 |
| Instance class | Small general-purpose instance type selected during module implementation |
| GPU | No |
| Spot | Optional later; avoid for first validation to reduce troubleshooting noise |
| NAT Gateway | No by default |
| Ingress / Load Balancer | No by default |
| Production data | No |
| Persistent data | No |
| CloudWatch control plane logs | Disabled or minimal short retention unless debugging |

The first EKS run should prove lifecycle and access, not production capacity.

### 5.2. Why desired node count starts at 1

A single node is enough to validate:

- cluster creation,
- node group join,
- `kubectl` access,
- namespace creation,
- basic scheduling,
- cleanup.

Two nodes can be used only if the specific task needs:

- basic rolling update behavior,
- pod distribution testing,
- higher scheduling capacity,
- minimal fault tolerance demonstration.

Do not start with three or more nodes in a portfolio dev account unless a task explicitly requires it.

---

## 6. Cost scenarios

These are planning scenarios, not final invoices. They intentionally use formulas and conservative language because EC2, storage, load balancer, NAT, public IPv4, and data transfer costs vary by region and configuration.

### 6.1. Scenario A — Plan-only EKS work

| Item | Expected AWS runtime cost |
|---|---:|
| Terraform formatting | `0 USD` |
| Terraform validation | `0 USD` |
| Terraform plan | `0 USD` for EKS runtime because no resources are created |
| Local `kind` validation | `0 USD` AWS runtime cost |

Use this for most early Sprint 13 commits.

### 6.2. Scenario B — Short-lived EKS validation window

Assumption:

```text
1 EKS cluster × 3 hours × 0.10 USD/hour = 0.30 USD control plane charge
```

Additional charges may include:

- EC2 worker nodes,
- EBS volumes,
- public IPv4 addresses,
- CloudWatch logs,
- data transfer,
- optional load balancer if created,
- optional NAT Gateway if created.

Expected posture:

```text
Short-lived validation should remain low-cost if NAT Gateway, Load Balancer, and unnecessary always-on services are avoided.
```

Before running this scenario, verify the exact expected cost in the AWS Pricing Calculator for the selected region and instance type.

### 6.3. Scenario C — Accidental 24-hour idle cluster

Assumption:

```text
1 EKS cluster × 24 hours × 0.10 USD/hour = 2.40 USD control plane charge
```

This does not include worker nodes, storage, networking, or logs.

The main risk is not the control plane alone. The larger risk is leaving supporting resources active, especially:

- worker nodes,
- NAT Gateway,
- load balancer,
- EBS volumes,
- public IPv4 addresses,
- CloudWatch logs.

### 6.4. Scenario D — Accidental month-long idle cluster

Assumption:

```text
1 EKS cluster × 730 hours × 0.10 USD/hour = 73.00 USD control plane charge
```

This excludes worker nodes and all supporting resources.

This is why a persistent EKS cluster is not allowed by default for Sprint 13.

### 6.5. Scenario E — Extended support cluster

Extended Kubernetes support is not acceptable for this project unless deliberately approved in a later maturity stage.

Reason:

```text
Extended support has a materially higher cluster-hour charge than standard support.
```

Guardrail:

- choose a standard-supported Kubernetes version,
- document the version in Terraform variables,
- avoid pinning old versions indefinitely.

---

## 7. Main EKS cost drivers

| Cost driver | Why it matters | Sprint 13 guardrail |
|---|---|---|
| Cluster lifetime | EKS control plane is charged while the cluster exists. | Same-day cleanup. |
| Worker nodes | EC2 cost can exceed control plane cost depending on instance type and lifetime. | 1 desired node initially, max 2. |
| NAT Gateway | Hourly and data processing charges can run while idle. | Avoid by default in early validation. |
| Load Balancer | May be created automatically by Kubernetes Service/Ingress patterns. | Avoid `LoadBalancer` services until ingress task. |
| CloudWatch logs | Ingestion and retention can accumulate cost. | Minimal logging and short retention for temporary clusters. |
| EBS volumes | Node and workload volumes can remain after failure or manual changes. | Verify unattached volumes after destroy. |
| Public IPv4 | Public addresses can add cost depending on resource design. | Keep design minimal and verify after cleanup. |
| Data transfer | Cross-AZ and internet transfer can add cost. | Avoid unnecessary traffic and multi-AZ demos early. |

---

## 8. Networking cost stance

### 8.1. Early validation stance

For early EKS validation, avoid expensive networking unless the task specifically requires it.

Default stance:

- no NAT Gateway by default,
- no production-style ingress by default,
- no multi-AZ high availability requirement for the first lifecycle proof,
- no persistent external traffic path until workload deployment maturity increases.

### 8.2. Trade-off: cost-aware dev vs production-like private nodes

| Option | Pros | Cons | Sprint 13 stance |
|---|---|---|---|
| Public-subnet dev nodes | Lower cost, simpler validation, no NAT required | Less production-like, must be treated as temporary dev only | Acceptable for short validation if security groups are restrictive. |
| Private nodes with NAT Gateway | More common production-style outbound access | NAT cost can continue while idle | Avoid by default in portfolio dev. |
| Private nodes with VPC endpoints | More secure and can reduce NAT dependency | More Terraform complexity and endpoint cost/design work | Good later maturity option. |

This trade-off should be revisited when the platform moves from lifecycle validation to production-like deployment.

---

## 9. Sizing and cost guardrails

### 9.1. Hard guardrails

These guardrails should block a real EKS apply unless explicitly overridden in a later task:

| Guardrail | Default |
|---|---|
| Cluster count | Maximum 1 dev cluster |
| Cluster lifetime | Same-day cleanup required |
| Desired nodes | 1 |
| Maximum nodes | 2 |
| NAT Gateway | Disabled/avoided by default |
| Load Balancer | Avoided until explicitly needed |
| RDS/MSK/OpenSearch | Not part of Sprint 13 EKS bootstrap |
| Production data | Not allowed |
| Extended support version | Not allowed |
| Apply automation | No unattended `apply -auto-approve` |

### 9.2. Soft guardrails

These guardrails should trigger review, not necessarily block work:

| Guardrail | Review trigger |
|---|---|
| More than 2 nodes | Explain why local/kind or 1 node is insufficient. |
| More than 3 hours runtime | Explain why evidence could not be captured sooner. |
| Any load balancer | Confirm that ingress/service validation is the task goal. |
| Any NAT Gateway | Confirm why VPC endpoints or public-subnet dev validation are not enough. |
| Any persistent volume | Confirm cleanup and data policy. |
| Any CloudWatch long retention | Confirm evidence/logging need and retention period. |

---

## 10. Cost review checklist before EKS apply

Before creating a real EKS cluster, complete this checklist.

```text
[ ] I know which AWS account/profile is active.
[ ] I know which AWS region is active.
[ ] I reviewed the Terraform plan.
[ ] I confirmed that the cluster uses required tags.
[ ] I confirmed that the node group is intentionally small.
[ ] I confirmed that NAT Gateway is not created by default.
[ ] I confirmed that LoadBalancer services are not part of this run unless required.
[ ] I confirmed that no RDS/MSK/OpenSearch resources are included in the EKS validation.
[ ] I confirmed that budget/alerting exists in the AWS account.
[ ] I have time to destroy the environment in the same session.
[ ] I know which evidence files/screenshots I need to capture.
[ ] I know how to verify cleanup after destroy.
```

If any item is unclear, do not apply yet.

---

## 11. Cleanup cost checklist after EKS destroy

After `terraform destroy`, verify that no hidden cost resources remain.

```text
[ ] EKS cluster deleted.
[ ] Managed node group deleted.
[ ] EC2 instances terminated.
[ ] Auto Scaling Group deleted.
[ ] Load Balancers deleted.
[ ] Target Groups deleted.
[ ] NAT Gateways deleted or confirmed not created.
[ ] Elastic IPs released if created.
[ ] Unattached EBS volumes deleted or intentionally retained with reason.
[ ] CloudWatch log groups reviewed for retention and cost.
[ ] Temporary ECR images reviewed if pushed.
[ ] Terraform state still matches expected resources.
[ ] AWS Console cost/billing view checked after validation window where practical.
```

Cleanup evidence should be saved in a later evidence commit under:

```text
docs/evidence/eks/
```

---

## 12. Recommended evidence for EKS cost discipline

When real EKS validation happens, collect evidence that proves cost awareness, not only cluster creation.

Recommended evidence:

| Evidence | Purpose |
|---|---|
| Terraform plan output | Shows what will be created before apply. |
| Screenshot or output of cluster/node count | Shows the environment is small. |
| Tags screenshot/output | Shows resources are traceable. |
| `kubectl get nodes` | Shows the node group joined. |
| `kubectl get namespaces` | Shows namespace bootstrap. |
| Terraform destroy output | Shows cleanup was performed. |
| AWS Console cleanup screenshot | Shows no cluster remains. |
| Cost note | Explains estimated control plane/node/network cost. |

---

## 13. Recommended first EKS validation narrative

A strong portfolio narrative for the first EKS run should be:

```text
I did not keep EKS running as a vanity resource. I used Terraform to create a minimal, tagged, short-lived dev cluster, validated access and basic Kubernetes bootstrap, captured evidence, then destroyed the environment and verified cleanup.
```

This is more mature than simply showing that a cluster exists.

---

## 14. Definition of Done for this cost review

This cost review is complete when:

- EKS standard and extended support pricing assumptions are documented,
- worker node and supporting service costs are explicitly separated from the control plane cost,
- local `kind` and plan-only modes are identified as zero AWS runtime cost paths,
- short-lived EKS validation has clear sizing boundaries,
- NAT Gateway, Load Balancer, CloudWatch, EBS, and public IPv4 cost risks are called out,
- pre-apply and post-destroy cost checklists are documented,
- cleanup expectations are connected to evidence collection,
- no AWS resources are created by this commit.

---

## 15. Open cost decisions for later Sprint 13 commits

| Decision | Why it is deferred |
|---|---|
| Exact EKS module input names | Belongs to module skeleton implementation. |
| Exact node instance type | Should be selected when Terraform node group module exists. |
| Public vs private node subnet implementation | Requires VPC/EKS module integration and security review. |
| Whether to use Spot | Useful later, but first validation should reduce troubleshooting variables. |
| Whether to add ingress/load balancer | Belongs after basic workload and namespace strategy. |
| Whether to use VPC endpoints | Good production-like option, but adds complexity and cost design. |
| EKS add-ons list | Should be introduced gradually after base cluster lifecycle works. |
| Full production cost estimate | Requires final architecture, traffic assumptions, HA requirements, and workload sizing. |

