# Gitignore Evidence Policy

Last reviewed: 2026-05-12

RetailOps keeps a strict boundary between evidence worth reviewing and generated output that should stay local.

## Policy Summary

| Area | Default | Reason |
|---|---|---|
| `docs/evidence/**` | Track | Curated evidence, screenshots, indexes, summaries, and reviewer-facing notes. |
| `ci-cd/reports/**` | Ignore | Generated output is usually volatile, local, large, or environment-specific. |
| `ci-cd/reports/**/README.md` | Track | Human-readable report indexes and policy notes. |
| `ci-cd/reports/**/*.evidence.md` | Track | Explicit evidence notes are reviewer-safe by design. |
| `ci-cd/reports/**/*-snapshot.txt` | Track when sanitized | Small text snapshots can support audit/recruiter evidence. |
| `ci-cd/reports/**/*-snapshot.json` | Track when sanitized | Small JSON snapshots can support audit/recruiter evidence. |
| `ci-cd/reports/iac/sprint-*-terraform-*.txt` | Track when sanitized | Controlled Terraform showcase snapshots are useful portfolio evidence. |
| `.terraform/`, Terraform state, binary plans | Ignore | They are environment-specific and can expose sensitive infrastructure details. |
| `node_modules/`, virtualenvs, caches, coverage XML | Ignore | They are reproducible generated artifacts. |
| raw `gitleaks.json`, non-snapshot Trivy files, Checkov/TFLint reports | Ignore by default | They can be noisy, stale, or require sanitization before review. |

## Current Root `.gitignore` Behavior

The root `.gitignore` now:

- ignores all files under `ci-cd/reports/**` by default,
- re-allows report directories so explicitly allowed files can be tracked,
- allows README/index evidence files,
- allows sanitized `*-snapshot.txt` and `*-snapshot.json`,
- allows sanitized Sprint Terraform snapshots,
- keeps API coverage, generated datasets, observability dumps, Ruff reports, raw scanner outputs, logs, and non-snapshot Terraform outputs ignored.

## What Should Be Committed

Commit:

- evidence indexes and README files,
- small sanitized screenshots,
- small sanitized scan summaries,
- Terraform validation/plan/apply/destroy snapshots that have been redacted,
- cleanup confirmations,
- Mermaid diagrams that explain evidence flow,
- policy documents that explain how to reproduce evidence.

## What Should Not Be Committed

Do not commit:

- credentials, tokens, `.env`, `.tfvars`, or local secret files,
- Terraform state, `.terraform/`, binary plan files, crash logs, or lock-info files,
- raw AWS resource IDs, account IDs, private ARNs, private console URLs, or notification emails,
- local virtualenvs, `node_modules/`, caches, build outputs, or coverage XML,
- large generated datasets,
- raw logs that include hostnames, local paths, request payloads, or secret-like strings.

## Promotion Workflow

When a local report becomes useful evidence:

1. Create a redacted summary or snapshot.
2. Name it with `*-snapshot.txt`, `*-snapshot.json`, or `*.evidence.md`.
3. Store it in the relevant `ci-cd/reports/<area>/` folder if it is tool output.
4. Store it in `docs/evidence/<area>/` if it is curated documentation or a screenshot.
5. Link it from `docs/evidence/index.md`.
6. Add freshness, scope, and limitations.

## Known Local Ignored Evidence Candidates

The repository currently has useful local outputs that remain ignored until they are sanitized and intentionally promoted:

- `ci-cd/reports/api/coverage.xml`
- `ci-cd/reports/data/generated/`
- `ci-cd/reports/observability/`
- `ci-cd/reports/ruff/`
- `ci-cd/reports/iac/checkov.*`
- `ci-cd/reports/iac/tflint.txt`
- `ci-cd/reports/security/gitleaks.json`
- non-snapshot Trivy outputs under `ci-cd/reports/security/`

These are not deleted because they may help with local validation, but they should not be committed as-is.
