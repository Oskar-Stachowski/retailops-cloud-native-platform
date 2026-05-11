# ADR-012: AWS cost control baseline

**Status:** Accepted
**Date:** Sprint 10
**Scope:** FinOps / budgets / cleanup / right-sizing

---

## Context

RetailOps is a portfolio and learning project. It should demonstrate cloud-native architecture without accidentally creating unnecessary AWS spend.

Cost control must be treated as part of architecture, not as a cleanup activity after resources are created.

Sprint 10 introduces budget awareness, short retention, temporary lifecycle tagging, and cleanup documentation before any production-like AWS showcase.

Related technical documentation:

- `docs/finops.md`
- `docs/cost-assumptions.md`
- `docs/cost-monitoring.md`
- `docs/right-sizing-lifecycle.md`
- `docs/runbooks/aws-cleanup-runbook.md`
- `docs/tagging-strategy.md`
- `infra/modules/budget/README.md`

---

## Decision

Use a cost-aware AWS baseline with:

- mandatory cost and lifecycle tags,
- low default monthly budget limit for the dev baseline,
- optional budget notifications without private email committed to the repository,
- short CloudWatch log retention for Sprint 10,
- explicit cleanup runbook,
- no EKS, RDS, MSK, OpenSearch, NAT Gateway, or long-retention observability unless a later decision justifies them.

---

## Options considered

### Option 1 — Build full target architecture immediately

Provision production-like AWS services early to make the project look impressive.

This creates strong visuals, but it risks unnecessary spend and makes the project harder to operate safely.

### Option 2 — Local-first plus small AWS foundation

Keep the application local-first and use Terraform to introduce only foundational AWS resources with cost guardrails.

This demonstrates senior DevOps judgment: architecture is planned, but cost is controlled.

### Option 3 — Avoid AWS entirely until the end

Delay all AWS work until the full application is complete.

This avoids cost but weakens the cloud-native infrastructure story and delays learning about Terraform/AWS integration.

---

## Decision outcome

Choose **Option 2: local-first plus small AWS foundation**.

The platform should prove business and delivery value locally, then introduce AWS resources gradually and intentionally.

---

## Consequences

Positive consequences:

- The project has a visible FinOps story before cloud spend starts.
- Tags support cost grouping and cleanup decisions.
- Budget configuration gives a safety signal for real AWS validation.
- Cleanup documentation reduces the risk of forgotten resources.

Trade-offs:

- The AWS environment remains incomplete compared with the target architecture.
- Some services shown in diagrams are intentionally deferred.
- Real cost estimates remain approximate until resources are actually applied and observed.

---

## Follow-up decisions

Future ADRs should decide:

- when to run a short real AWS apply,
- exact destroy and evidence workflow after AWS showcase,
- whether EKS is justified or ECS is enough for the portfolio goal,
- whether managed services should be created only temporarily,
- which cost findings become hard CI gates.
