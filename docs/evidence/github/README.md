# GitHub branch protection evidence

Captured on 2026-09-25 at 11:28:41 UTC with `main` at
`46218000c78e49edca6ec396bbfa2314a1645be2`.

The [API snapshot](main-branch-protection.json) records the exact request and
the subsequent authenticated read of GitHub's branch-protection settings.
It contains configuration metadata only; no credentials are included.

## Active settings

| Control | Verified value |
|---|---|
| Protected branch | `main`, `protected: true` |
| Pull request required | Enabled |
| Required status | `required-result`, GitHub Actions app ID `15368` |
| PR up to date with base | Required (`strict: true`) |
| Enforcement for administrators | Enabled |
| PR bypass allowances | None |
| Force pushes / branch deletion | Disabled / disabled |
| Conversation resolution | Required |
| Approving reviews | 0, for solo maintenance |
| Dismiss stale approvals | Enabled |

Mandatory PRs and passing CI are enforced without requiring a second person
to approve the sole maintainer's changes. Code-owner approval and last-push
approval are not required. The branch remains open for normal PR merges;
it is not locked or restricted to linear history.

## Verification

1. Read `GET /repos/Oskar-Stachowski/retailops-cloud-native-platform/branches/main`
   and the branch-protection endpoint; no protection or rulesets existed.
2. Confirmed that the successful check was named `required-result` and issued
   by GitHub Actions, rather than using the workflow/job display label as a
   check context.
3. Applied protection and independently read both endpoints again.
4. Compared the returned provider, status context, strict mode, review
   settings, administrator enforcement and push/deletion controls with the
   requested settings. All assertions passed.

The [successful full CI run on main](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36128412201)
establishes that the selected required check exists and can pass.
This snapshot proves the configured controls at capture time. No direct
push, force push or deletion test was attempted against `main`.

The [GitHub branch settings](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/settings/branches)
are the live source of truth. Re-capture the API response after policy
changes and update [the policy](../../governance/branch-protection.md) and
[evidence ledger](../index.md).
