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

These changes address parts of the audit's CI and scanning findings. They do
not close the entire portfolio backlog or establish production readiness.
Branch protection enforcement still requires separate GitHub settings
evidence, as described in [the policy](../governance/branch-protection.md).

## Synchronization scope

The local branch inventory was compared with freshly fetched `origin/main`
(`5dc136e`). All implementation branches were already contained in `main`
except the CI correction in PR #30. Two old `repo-quality-hardening` commits
contain ignore rules and an infrastructure entrypoint convention that have
since been superseded; merging their outdated text would regress current
documentation. The remaining `test/ci-check-discovery` commit is empty.

The synchronization includes the pending CI changes, their documentation and
this audit. Personal planning directories, environment files, Terraform
state/plans, generated datasets, dependencies and raw local reports are not
release evidence. Curated evidence remains indexed under
[`docs/evidence/`](../evidence/index.md).

Open Dependabot pull requests are separate dependency upgrades and need their
own validation. They are not missing local implementation work.
