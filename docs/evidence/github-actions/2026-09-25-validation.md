# Dependency refresh validation — 2026-09-25

This sanitized summary records GitHub Actions results reviewed on 2026-09-25.
It does not refresh historical screenshots, AWS runs or ML model snapshots.

## Revisions and runs

| Change | Tested PR head | Required CI |
|---|---|---|
| [Frontend #34](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/34) | `a7860bdab31082737c5fff341d8d7ec6aa3d7c59` | [36131025187](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36131025187) — passed |
| [Python #35](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/35) | `0294449a3d8c120ac75e3984b723d6e3a82dd162` | [36132321905](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36132321905) — passed |
| [Images #36](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/36) | `4d41c93dbcb90e598cbed4f3adc3b785d82d9567` | [36133335007](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007) — all 23 jobs passed |

The final run includes the merged frontend/Python changes. GitHub validated
the PR integration revision; the table identifies each PR head. After #36
merged, main was `44f7404010b55eba3d9bacd888d2dc7bb9797180`.

## Verified outcomes from the final run

| Area | Recorded result | Source |
|---|---|---|
| API | 302 tests passed; branch coverage 83.82% (gate: 80%); PostgreSQL migrations and seed passed. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499742) |
| Frontend | 36 tests passed; lint passed. Production and Docker builds also passed. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499709) |
| Python dependencies | No known vulnerabilities reported for runtime and development requirements. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499907) |
| Frontend dependencies | npm audit including development tools passed its HIGH/CRITICAL threshold. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499928) |
| Secrets | Gitleaks reported no leaks in the configured scan scope. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499971) |
| Filesystem | Trivy passed the fixed HIGH/CRITICAL gate. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499921) |
| API image | Trivy passed the fixed CRITICAL gate. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499872) |
| Frontend image | Nginx 1.31-alpine passed the fixed CRITICAL gate. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499896) |
| Runtime | Fresh builds, Compose startup and API/frontend HTTP, streaming and observability smoke passed. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065582737) |
| Scanner | Security container started and printed Version: 0.74.0. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499830) |
| IaC | Checkov passed with documented exceptions; TFLint, Terraform validation and Kubernetes schema/policy gates also passed. | [Job](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/job/108065499817) |

The API run also recorded one Starlette TestClient deprecation warning about
httpx. It did not fail the tests. Scan thresholds and accepted Checkov
exceptions are documented in [Security](../../../security/README.md).
Passing image scans does not mean zero findings at every severity or for
unfixed vulnerabilities.

## Retained evidence

Artifacts were present and unexpired when reviewed. These run-specific links
require repository access; standard 14-day retention expires on 2026-10-09.
This summary remains in Git after raw artifact expiry.

- [api-coverage-evidence](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10863008043)
- [frontend-quality-evidence](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10863027729)
- [security-ci-evidence](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10862192799)
- [docker-compose-ci-evidence](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10862913299)
- [iac-checkov-reports](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10863032891)
- [iac-tflint-report](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36133335007/artifacts/10863142651)

## Boundaries and follow-up

This run did not execute Playwright browser journeys. Browser smoke and
screenshot capture were manually invoked at this revision. It did not deploy
AWS/EKS, publish release images, validate production authentication, re-run
Jenkins or refresh the historical ML training snapshot.

Main protection required a successful `required-result` and an up-to-date PR
before each merge. Superseded Dependabot PRs #21, #22, #31 and #32 were closed.
The only unique commit in PR #16 was empty; the obsolete PR was closed after
comparison with current main.

