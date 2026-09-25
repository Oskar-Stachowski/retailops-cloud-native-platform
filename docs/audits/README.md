# Repository audits

Reviewed for repository synchronization: 2026-09-25.

The [DevOps portfolio audit](retailops-devops-portfolio-audit.md) is a historical
assessment from 2026-07-14 of commit `bd85ce4`. Its test counts, findings and
recommendations describe that snapshot. They are not a fresh validation of
the current application or AWS environment.

## Changes since the audit

- `bfae630` replaced the shallow Required CI workflow with full reusable domain
  gates, tested path detection and a final result that rejects missing,
  skipped, cancelled or failed required gates.
- `62b6a93` addressed blocking Checkov findings. Accepted exceptions remain
  documented in [the security documentation](../../security/README.md).
- The synchronization update separates uncredentialed Terraform validation
  from the manual AWS OIDC plan workflow and removes duplicate automatic
  triggers from the reusable domain workflows. See
  [the CI contract](../governance/github-actions-ci.md).
- The first fresh [Required CI run](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36126919676)
  caught newly reported React Router vulnerabilities in version 7.15.0.
  React Router and React Router DOM were updated together to 7.18.4.
  Local frontend validation passed all 36 tests, lint and production build;
  `npm audit --omit=dev` reported zero vulnerabilities after the update.

These changes address parts of the audit's CI and scanning findings. They do
not close the entire portfolio backlog or establish production readiness.
The initial synchronization found `main` unprotected on 2026-09-25.
Protection was enabled later that day: mandatory PRs, the `required-result`
check, up-to-date branches, conversation resolution and administrator
enforcement, with force pushes and deletion disabled. See
[the active policy](../governance/branch-protection.md) and
[captured GitHub settings](../evidence/github/README.md).

## Dependency refresh completed

PRs [#34](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/34),
[#35](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/35)
and [#36](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/36)
refreshed frontend and Python dependencies, upgraded Nginx to `1.31-alpine`,
and aligned Compose/CI Trivy at `0.74.0`. Both dependency audits now include
development tools. All 23 jobs in the final Required CI run passed, including
302 backend tests with 83.82% coverage and 36 frontend tests. See the dated
[validation summary](../evidence/github-actions/2026-09-25-validation.md) for
exact revisions, run links, artifacts and scan thresholds.

## Synchronization scope

The local branch inventory was compared with freshly fetched `origin/main`
(`5dc136e`). All implementation branches were already contained in `main`
except the CI correction in PR #30. Two old `repo-quality-hardening` commits
contain ignore rules and an infrastructure entrypoint convention that have
since been superseded; merging their outdated text would regress current
documentation. The remaining `test/ci-check-discovery` commit is empty.

The synchronization included the CI changes, their documentation and
this audit. Personal planning directories, environment files, Terraform
state/plans, generated datasets, dependencies and raw local reports are not
release evidence. Curated evidence remains indexed under
[`docs/evidence/`](../evidence/index.md).

The separate dependency review is complete: PRs #31 and #32 were replaced by
#35 and #34, and image PRs #21 and #22 by #36. The superseded PRs were closed
after their replacements passed Required CI and merged. The resulting main
revision is `44f7404010b55eba3d9bacd888d2dc7bb9797180`.

PR [#16](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/16)
was closed after comparison with current main: its only unique commit,
`e46ad23`, is empty and its parent is already an ancestor of main. Its old PR
comparison contains historical changes already integrated into main; closing
it omits no implementation work.

## Remaining work

- Extend the seven Chromium journeys in Required CI with broader accessibility
  and browser coverage when needed; screenshot capture remains opt-in.
- Prove recovery and deployment behavior separately from test/build gates.
- Refresh historical Jenkins, runtime and ML evidence only after a new execution.

The [current roadmap](../roadmap/future-improvements/README.md) tracks these gaps.
Historical audit findings remain unchanged so their original context is preserved.
