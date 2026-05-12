# Evidence Cleanup Report

Date: 2026-05-12
Branch: `repository-audit-findings`

## Summary

The evidence layer was reorganized into two clear areas:

- `docs/evidence/` for curated, human-readable portfolio and audit evidence.
- `ci-cd/reports/` for raw or semi-raw generated outputs and sanitized snapshots.

The cleanup keeps recruiter-facing screenshots and indexes in `docs/evidence/`, while Terraform and Trivy command outputs now live under `ci-cd/reports/` with explicit snapshot naming.

## Files Moved

| From | To | Reason |
|---|---|---|
| `docs/evidence/Jenkins Stage View.png` | `docs/evidence/jenkins/jenkins-stage-view.png` | Put Jenkins screenshots in a dedicated evidence folder and normalize filename casing. |
| `docs/evidence/Jenkins Status and Artifacts.png` | `docs/evidence/jenkins/jenkins-status-and-artifacts.png` | Put Jenkins screenshots in a dedicated evidence folder and normalize filename casing. |
| `docs/evidence/sprint-10/README.md` | `docs/evidence/aws/README.md` | Move curated AWS/Terraform showcase notes out of sprint naming into durable evidence taxonomy. |
| `docs/evidence/sprint-10/aws-cleanup-confirmation.md` | `docs/evidence/aws/aws-cleanup-confirmation.md` | Keep cleanup note with curated AWS evidence. |
| `docs/evidence/sprint-10/aws-console-budget.png` | `docs/evidence/aws/aws-console-budget.png` | Keep recruiter-facing AWS screenshot with curated AWS evidence. |
| `docs/evidence/sprint-10/aws-console-cloudwatch.png` | `docs/evidence/aws/aws-console-cloudwatch.png` | Keep recruiter-facing AWS screenshot with curated AWS evidence. |
| `docs/evidence/sprint-10/aws-console-ecr.png` | `docs/evidence/aws/aws-console-ecr.png` | Keep recruiter-facing AWS screenshot with curated AWS evidence. |
| `docs/evidence/sprint-10/aws-console-iam.png` | `docs/evidence/aws/aws-console-iam.png` | Keep recruiter-facing AWS screenshot with curated AWS evidence. |
| `docs/evidence/sprint-10/aws-console-vpc.png` | `docs/evidence/aws/aws-console-vpc.png` | Keep recruiter-facing AWS screenshot with curated AWS evidence. |
| `docs/evidence/sprint-10/terraform-apply.txt` | `ci-cd/reports/iac/sprint-10-terraform-apply.txt` | Terraform command output belongs with generated IaC reports. |
| `docs/evidence/sprint-10/terraform-destroy.txt` | `ci-cd/reports/iac/sprint-10-terraform-destroy.txt` | Terraform command output belongs with generated IaC reports. |
| `docs/evidence/sprint-10/terraform-plan-dev.txt` | `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt` | Terraform command output belongs with generated IaC reports. |
| `docs/evidence/sprint-10/terraform-validate.txt` | `ci-cd/reports/iac/sprint-10-terraform-validate.txt` | Terraform command output belongs with generated IaC reports. |
| `docs/evidence/trivy-api-image.txt` | `ci-cd/reports/security/trivy-api-image-snapshot.txt` | Security scanner output belongs with generated security reports and needs snapshot naming. |
| `docs/evidence/trivy-frontend-image.txt` | `ci-cd/reports/security/trivy-frontend-image-snapshot.txt` | Security scanner output belongs with generated security reports and needs snapshot naming. |
| `docs/evidence/trivy-fs.txt` | `ci-cd/reports/security/trivy-fs-snapshot.txt` | Security scanner output belongs with generated security reports and needs snapshot naming. |

## Files Renamed

The Jenkins screenshots and Trivy outputs were renamed to kebab-case or explicit snapshot names. Terraform files received the `sprint-10-` prefix after moving to `ci-cd/reports/iac/` so they do not collide with fresh local report outputs.

## Files Deleted

No evidence file was permanently deleted.

The empty `docs/evidence/sprint-10/` directory was removed after all tracked files were moved. Git does not track empty directories, so this does not delete evidence content.

The empty local `ci-cd/reports/jenkins/` directory was also removed because it contained no evidence files and would otherwise keep an unnecessary empty report bucket in the generated repository structure snapshot.

Local `.DS_Store` files and other ignored local outputs were not deleted in this cleanup; they remain ignored and should not be committed.

## New Evidence Index and Policy Files

| File | Purpose |
|---|---|
| `docs/evidence/README.md` | Main evidence entry point. |
| `docs/evidence/index.md` | Evidence inventory with proof, project area, audience, and validation notes. |
| `docs/evidence/jenkins/README.md` | Jenkins evidence index and refresh checklist. |
| `docs/evidence/gptimages-index.md` | GPTimages usage, status, and recommended action index. |
| `docs/evidence/gitignore-evidence-policy.md` | Tracked versus ignored evidence policy. |
| `docs/evidence/evidence-folder-map.md` | Final folder structure and evidence flow diagrams. |
| `ci-cd/reports/README.md` | Raw report tracking policy. |
| `ci-cd/reports/iac/README.md` | IaC report snapshot index. |
| `ci-cd/reports/security/README.md` | Security report snapshot index. |

## `.gitignore` Changes

The root `.gitignore` now:

- ignores `ci-cd/reports/**` by default,
- re-allows report directories so explicit exceptions work,
- tracks `ci-cd/reports/**/README.md`,
- tracks `ci-cd/reports/**/*.evidence.md`,
- tracks sanitized `*-snapshot.txt` and `*-snapshot.json`,
- tracks sanitized Sprint Terraform snapshots,
- keeps local API coverage, generated data, observability dumps, Ruff reports, raw Gitleaks JSON, raw Trivy output, logs, and non-snapshot Terraform output ignored.

## Broken Links Fixed

Updated references in:

- `README.md`
- `ci-cd/README.md`
- `docs/cost-monitoring.md`
- `docs/evidence/aws/README.md`
- `docs/evidence/aws/aws-cleanup-confirmation.md`
- `docs/runbooks/aws-cleanup-runbook.md`
- `infra/README.md`
- `LOCAL_ADVANCED_ROADMAP/retailops-production-readiness-checklist-audited.md` local ignored checklist copy

The static repository tree snapshot was regenerated after the evidence moves.

## Diagrams Updated

Updated or added Mermaid diagrams for:

- AWS/Terraform showcase evidence flow in `docs/evidence/aws/README.md`.
- Jenkins evidence flow in `docs/evidence/jenkins/README.md`.
- Curated versus raw evidence flow in `docs/evidence/evidence-folder-map.md`.
- AWS/Terraform evidence flow in `docs/evidence/evidence-folder-map.md`.
- CI/CD evidence flow in `docs/evidence/evidence-folder-map.md`.
- Security evidence flow in `docs/evidence/evidence-folder-map.md`.
- Observability evidence flow in `docs/evidence/evidence-folder-map.md`.
- Future Kubernetes/Helm evidence flow in `docs/evidence/evidence-folder-map.md`.
- Future MLOps/GenAI evidence flow in `docs/evidence/evidence-folder-map.md`.

## GPTimages Review Summary

- Total GPT images reviewed: 21.
- Images referenced by tracked docs: 18.
- Images not referenced by tracked docs except the repository tree snapshot: 3.
- No images were generated.
- No images were deleted.

Unused but retained images:

- `GPTimages/Data-Flow.png`
- `GPTimages/Future-Growth-Perspective.png`
- `GPTimages/retailops_testing_roadmap_infographic.png`

They were kept because they may still be useful for portfolio storytelling or future documentation, but they should either be referenced intentionally or removed in a later cleanup.

## Commands Run and Results

| Command | Result |
|---|---|
| `git status --short --branch` | Confirmed the starting branch was clean before cleanup and reviewed the final working tree. |
| `find docs/evidence ci-cd/reports GPTimages -maxdepth 3 -type f` | Inventory collected for evidence files, reports, screenshots, and generated images. |
| `git ls-files docs/evidence ci-cd/reports GPTimages` | Confirmed which evidence artifacts were tracked before cleanup. |
| `rg` searches for old evidence paths and moved filenames | Found stale references and confirmed most were resolved before final validation. |
| `make docs-repo-structure` | Regenerated `docs/repo-structure.txt` after the cleanup. |
| `git check-ignore` evidence policy checks | Confirmed volatile local reports remain ignored; allowed evidence paths produced no ignore match. |
| Corrected `git check-ignore` loop using variable `p` | Reran after an initial zsh `path` variable collision; final policy check succeeded. |
| `git diff --check` | Passed with no whitespace errors. |

## Remaining Risks

- Jenkins screenshots are static and do not embed branch, commit SHA, or run timestamp in the markdown.
- AWS screenshots are static; the Terraform snapshots are sanitized summaries, not full raw command logs.
- `ci-cd/reports/security/trivy-frontend-image-snapshot.txt` proves scanning exists but currently records critical frontend image vulnerabilities.
- Observability, Ruff, Checkov, TFLint, API coverage, and Gitleaks local outputs exist but are ignored until sanitized snapshots are created.
- GPTimages are useful for storytelling but must not be treated as implementation evidence by themselves.
- `docs/repo-structure.txt` is a static generated tree and can become stale again.

## Next Recommended Evidence to Collect

1. Clean replacement Trivy frontend image snapshot after base image remediation.
2. Sanitized Gitleaks summary snapshot.
3. Sanitized Checkov summary snapshot.
4. Sanitized TFLint summary snapshot.
5. API coverage summary in Markdown rather than raw XML.
6. Docker Compose smoke test snapshot with command, date, and result.
7. GitHub Actions run screenshots or artifact links for API, frontend, Docker, security, and Terraform workflows.
8. Fresh Jenkins run screenshots with branch, commit SHA, and run date.
9. Observability dashboard screenshots and Prometheus query snapshots.
10. Kubernetes manifest validation evidence when Kubernetes scope becomes implemented.
