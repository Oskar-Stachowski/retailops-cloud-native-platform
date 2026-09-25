# Future Improvements Roadmap

Reviewed against main `44f7404010b55eba3d9bacd888d2dc7bb9797180` on 2026-09-25.
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

## Next priorities

| Priority | Work | Completion evidence |
|---:|---|---|
| 1 | Extend browser coverage where product changes require it; add accessibility and cross-browser checks. | Build on the seven critical Chromium journeys and retain traces for failures. |
| 2 | Exercise database restore and application rollback on an isolated local stack. | Dated recovery run with before/after checks and measured recovery time. |
| 3 | Define a release/tag policy and publish the same tested image with digest, SBOM and provenance. | One reviewable release linked to its CI run and immutable image identity. Registry/environment selection is a separate deployment decision. |
| 4 | Exercise Kubernetes workloads on a local cluster before cloud deployment. | Pods, migrations, seed, probes, ingress, runtime smoke and cleanup evidence; current schema/policy checks remain necessary but insufficient. |
| 5 | Verify Terraform remote state and drift workflow before another AWS showcase. | Reviewed backend/access design, state migration and plan-only drift evidence; refresh cost/cleanup records after any actual cloud run. |
| 6 | Refresh observability/SLO and Jenkins evidence through actual execution. | Dated metric/alert checks and Jenkins run tied to a commit; preserve older screenshots as historical. |
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
