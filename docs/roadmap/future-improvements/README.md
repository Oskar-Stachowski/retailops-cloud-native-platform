# Future Improvements Roadmap

Reviewed against main `7188d813dac0023a5daa99b7aa0210b3f823641a` on 2026-09-26.
This is a prioritized plan, not implementation evidence. Dated results live in
[the evidence index](../../evidence/index.md).

## Completed foundation

The [September validation summary](../../evidence/github-actions/2026-09-25-validation.md)
records 23 successful Required CI jobs after the dependency and image refresh.

- Main requires an up-to-date PR and successful `required-result`; administrators
  are covered and force pushes/deletion are blocked.
- API tests, coverage, frontend tests/lint/build, image builds, and Compose
  API/frontend HTTP, streaming and observability smoke checks run in CI.
- Runtime and development dependencies are audited. Gitleaks, Trivy, TFLint,
  Checkov and Kubernetes schema/policy checks are blocking gates with documented
  thresholds and accepted exceptions.
- Nginx is on `1.31-alpine`; Compose and CI use Trivy `0.74.0`. The refreshed
  image scans passed their fixed-CRITICAL gate. This supersedes the old frontend
  image finding as a current blocker, without erasing its historical snapshot.
- Coverage and scanner results have dated summaries and run/artifact links.
- Local ML training/evaluation, repository SBOM snapshots, Kubernetes manifests,
  Terraform foundation and runbooks already exist. Their presence does not
  establish a production deployment or fresh execution of historical evidence.

Critical Chromium coverage is now wired into the Docker gate for dashboard,
product drill-down, alert/recommendation decisions, read-only access and API
retry. See the [browser coverage matrix](../../evidence/e2e/README.md). The dated
September dependency summary above retains its original pre-E2E scope.

A [dated database recovery drill](../../evidence/db/README.md) now verifies
backup/restore, all public-table fingerprints, workflow history, idempotent
replay and post-restore writes in an isolated local project. It also runs in
the Docker CI gate. A [versioned application rollback drill](../../evidence/releases/README.md)
also verifies image identity, same-schema migration compatibility, update,
failure detection, rollback and preservation of new-version writes.

[Release v0.2.1](../../evidence/releases/2026-09-26-registry.md), verified on
2026-09-26, now publishes the same tested Linux AMD64 API/frontend artifacts to
GHCR, verifies signed image provenance/SPDX SBOMs on a fresh runner, and repeats
the rollback drill after digest pulls. An annotated tag and durable evidence
bundle are published only after that verification succeeds.

Step 4, [local Kubernetes runtime](../../evidence/kubernetes/2026-09-26-runtime.md),
is now verified on ARM64 and AMD64. All 24 Required CI jobs passed, including
actual kind startup, Traefik ingress, enforced NetworkPolicy, migration/seed/topic
Jobs, streaming deduplication, browser checks, PVC persistence through restarts,
same-schema update/rollback and cleanup. This uses native source builds, separate
from the signed registry artifacts above. EKS remains future work.

Step 5 [audited state and implemented guarded plan/drift review](../../evidence/aws/2026-09-26-state-drift.md).
The current account has no matching managed foundation or state bucket; the
retained GitHub read-only plan role was verified and preserved. Baseline plans,
real local-file drift/migration tests and backend configuration checks have dated
evidence. S3/KMS configuration, scoped lock access and the migration/recovery
runbook are ready for review at the next cloud activation. No live AWS state was
migrated, and live S3 locking/recovery remains to be proven then.

Step 6 [refreshed monitoring and Jenkins through actual execution](../../evidence/observability/2026-09-26-validation.md).
Isolated ARM64/AMD64 stacks proved ingested metrics, Grafana queries, a real
two-minute alert hold, firing, recovery/resolution and cleanup. Jenkins ran the
repository pipeline and archived matching source identity. The local scrape SLO
has explicit coverage requirements; 30-day compliance and notification delivery
remain unproven. Historical screenshots are preserved.

## Next priorities

| Priority | Work | Completion evidence |
|---:|---|---|
| 1 | Extend browser coverage where product changes require it; add accessibility and cross-browser checks. | Build on the seven critical Chromium journeys and retain traces for failures. |
| 2 | Extend recovery/rollback drills when schema or deployment behavior changes. The current same-schema application rollback and database restore are verified. | Keep dated checks and timings for each supported migration/deployment path. |
| 3 | Maintain verified registry releases; add selection of retained published predecessors as release history grows. The first release bootstraps a freshly tested predecessor. | Build on the published v0.2.1 evidence and retain exact digests, signed bundles and runtime verification for each release. |
| 4 | Maintain the completed local Kubernetes gate; extend it when deployment or schema behavior changes. | [ARM64/AMD64 runtime and persistence evidence](../../evidence/kubernetes/2026-09-26-runtime.md), 24 successful CI jobs and automatic cleanup. Cloud deployment and cluster-loss recovery remain separate scope. |
| 5 | Maintain the verified account-pinned baseline/drift workflow; activate the prepared S3/KMS backend when a managed deployment is needed. | [State audit and test evidence](../../evidence/aws/2026-09-26-state-drift.md) complete for the current state-less environment. A future cloud activation must add live state migration, lock/recovery and drift evidence. |
| 6 | Maintain the completed monitoring incident drill and actual Jenkins validation. Add request SLIs and notification delivery when operational scope requires them. | [Dated ARM64/AMD64 alert and Jenkins evidence](../../evidence/observability/2026-09-26-validation.md); 24 successful CI jobs, explicit SLO limits and historical screenshots preserved. |
| 7 | Re-evaluate ML artifacts after dependency/data changes and define model promotion criteria. | New evaluation, model metadata and reproducibility record; historical model binaries retain their original capture dates. |
| 8 | Add Helm packaging or further deployment automation when a validated runtime requires it. | Lint/render/install/upgrade/rollback evidence for the chosen environment. |

## Claim boundaries

- Passing image scans does not mean zero vulnerabilities at every severity or
  for unfixed issues. See [security policy](../../../security/README.md).
- Current CI proves local-stack behavior and infrastructure validation, not an
  always-on AWS/EKS environment, cloud release promotion or production MLOps.
- Demo user switching is not production authentication.
- Historical screenshots, audits, SBOMs and model snapshots are not fresh runs.

Every completed item must link to source/configuration and a dated result.
Refresh this roadmap when that evidence lands; do not mark work complete from
plans or diagrams alone.
