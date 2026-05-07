# ADR-011: AWS networking baseline

**Status:** Accepted  
**Date:** Sprint 10  
**Scope:** AWS VPC / subnets / routing / network cost boundary

---

## Context

RetailOps needs an AWS network foundation for future cloud workloads such as EKS, RDS, ECR-connected delivery, observability, and controlled ingress.

The project does not yet need a full production network. Sprint 10 should create a plan-reviewable baseline that teaches correct AWS networking boundaries without introducing avoidable always-on cost.

Related technical documentation:

- `docs/networking-baseline.md`
- `docs/diagrams/networking-baseline.mmd`
- `infra/modules/vpc/README.md`

---

## Decision

Use a small AWS VPC baseline with:

- one development VPC,
- two public subnets,
- two private subnets,
- public route table connected to an Internet Gateway,
- private route tables without NAT Gateway,
- baseline application and database security groups,
- explicit output showing that NAT Gateway is disabled.

The current baseline is allowed to be visible in `terraform plan`, but `terraform apply` remains a separate decision.

---

## Options considered

### Option 1 — No VPC module yet

Keep Terraform limited to documentation, tags, and empty scaffolding.

This is safest from a cost perspective, but it does not demonstrate meaningful AWS infrastructure design.

### Option 2 — Minimal VPC baseline without NAT Gateway

Create the core network shape while avoiding NAT Gateway and other always-on components.

This gives enough architecture to support future EKS/RDS decisions while keeping the first AWS baseline cost-aware.

### Option 3 — Production-style VPC with NAT, endpoints, inspection, and multi-environment design

Create a more complete enterprise network immediately.

This is closer to production, but it creates complexity and possible cost before workloads justify it.

---

## Decision outcome

Choose **Option 2: minimal VPC baseline without NAT Gateway**.

This is the right Sprint 10 balance: real AWS architecture, but still controlled, understandable, and cost-aware.

---

## Consequences

Positive consequences:

- The project now has a clear public/private subnet model.
- Future EKS, RDS, load balancer, and observability decisions have a network foundation.
- NAT Gateway cost is avoided until private workloads need outbound internet access.
- Security groups communicate application/database separation early.

Trade-offs:

- Private subnets currently do not have outbound internet access.
- Future private workloads may require NAT Gateway, VPC endpoints, or another egress strategy.
- The public subnet behavior must be reviewed before placing any workload directly there.

---

## Follow-up decisions

Future ADRs should decide:

- whether EKS should use public or private node groups,
- when NAT Gateway is justified,
- whether VPC endpoints reduce NAT cost for AWS service access,
- whether RDS needs separate database subnet groups,
- ingress strategy for public traffic.
