# CI/CD

RetailOps validates local application and infrastructure behavior before cloud
activation. Protected GitHub Required CI is the merge gate. Jenkins is an
additional, manually executed local validation pipeline; it does not deploy or
promote cloud workloads.

## Current ownership

| Layer | Responsibility |
|---|---|
| `make ci-local` | Data quality/contracts, backend lint/types/security/tests/coverage, frontend tests/lint/build |
| GitHub Required CI | Required aggregate result over the selected API, frontend, data, Docker, Kubernetes, Terraform and security gates |
| Docker runtime gate | Isolated build, API/frontend/streaming checks, Grafana/Prometheus incident drill and seven Chromium journeys; database recovery and versioned rollback drills follow |
| Local Kubernetes gate | Real kind workloads, persistence, network policy, update/rollback and cleanup |
| Registry release workflow | Controlled publication and verification of signed GHCR release artifacts |
| Terraform plan/drift workflow | Account-pinned, read-only baseline/plan review; no automatic apply |
| Jenkins | Fresh checkout, dependency installation, data quality, local CI and mandatory isolated Compose runtime/alert validation |

Cloud workload deployment, EKS, Helm promotion and production secrets management
remain future work. The AWS foundation was exercised historically; its current
state audit and backend activation boundaries are linked from the
[evidence index](../docs/evidence/index.md).

## Local commands

| Command | Purpose |
|---|---|
| `make install` | Install backend and frontend dependencies |
| `make ci-local` | Run local code and data checks |
| `make compose-ci` | Build and test a unique disposable Compose project, then remove its resources |
| `make observability-smoke` | Inspect an already running development monitoring stack |
| `make security-scan` | Run local secret, filesystem and image scans; requires the documented scanner toolchain |
| `make k8s-runtime-drill` | Exercise an isolated local Kubernetes deployment |
| `make db-recovery-drill` | Verify database backup and restore |
| `make release-drill` | Verify a versioned update and compatible application rollback |

`make compose-ci` allocates unique images, loopback ports, project and volumes.
It temporarily stops its own API to validate a real two-minute outage alert.
Its runner performs scoped cleanup on success and failure. It does not use the
default development project's volumes. GitHub enables the browser gate with
`COMPOSE_BROWSER_TESTS=1`; Jenkins runs the HTTP, streaming and monitoring checks.

To inspect a failed run, read `ci-cd/reports/docker-compose-logs.txt`,
`ci-cd/reports/docker/isolated-runtime.json`, and
`ci-cd/reports/observability/incident-drill.json`. The disposable stack has already
been removed; `docker compose logs` without its project would address a different
stack. Reproduce with `make compose-ci`.

## Jenkins execution

Create a Pipeline job with **Pipeline script from SCM**, select the trusted
repository revision and use `Jenkinsfile`. A trusted agent needs Git, Make,
Python 3.11, Node/npm and Docker Compose. The agent executes repository code with
Docker access. Keep the controller private and authenticated.

The only pipeline parameter is `DATA_PROFILE` (`small` by default, or `medium`).
Compose validation and the incident drill are mandatory. The old
`RUN_COMPOSE_SMOKE`, `RUN_SECURITY_SCAN` and `DEPLOY_TARGET` parameters and fake
cloud deployment stages have been removed. Broader security checks remain in
protected GitHub Required CI and are not claimed as Jenkins stages.

The pipeline cleans its own workspace before checkout and archives an explicit
allowlist: its commit/result summary, coverage, data quality reports and the
runtime/incident reports. It never runs a default-project `docker compose down`.
A 45-minute timeout, serial builds and retention of 20 builds are configured.

The [dated Jenkins run](../docs/evidence/jenkins/2026-09-26-validation.md) records
an actual execution, stage results, source identity and archived artifact hashes.
Older screenshots remain historical.

## GitHub governance and security

[CI governance](../docs/governance/github-actions-ci.md) and
[main protection](../docs/governance/branch-protection.md) describe the required
`required-result`, up-to-date PR policy and protection of administrators.
The classifier and its contract tests run even for documentation-only PRs.
Unknown/shared paths select all implementation gates; documentation changes
retain the aggregate merge check without rebuilding unchanged application code.

Security thresholds and accepted exceptions are defined in
[the security policy](../security/README.md), rather than duplicated here.
Dependency audits, secret scanning, image/filesystem scanning, IaC checks and
Kubernetes policy checks have blocking gates. A passing scan is not a guarantee
of zero unfixed or lower-severity findings.

## Evidence contract

Generated reports belong under `ci-cd/reports/` and are ignored by default.
GitHub uploads workflow artifacts; Jenkins archives its allowlist. Promote only
reviewed, sanitized snapshots under `docs/evidence/`, recording UTC time, exact
commit, command/run, result and limits. Preserve historical screenshots with
their original context. The [evidence index](../docs/evidence/index.md) is the
entry point; [report policy](reports/README.md) describes raw outputs.

The [monitoring validation](../docs/evidence/observability/2026-09-26-validation.md)
checks real samples, Grafana queries, alert firing and resolution. Its
[local scrape SLO](../docs/observability/slo.md) is explicitly separate from user
request availability, 30-day compliance and notification delivery.
