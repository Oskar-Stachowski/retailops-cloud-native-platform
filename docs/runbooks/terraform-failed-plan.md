# Terraform Failed Plan Runbook

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** Terraform / AWS Foundation / Operations  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(runbook): add Terraform drift and failed plan runbooks`

---

## 1. Purpose

This runbook explains how to troubleshoot failed Terraform validation or plan runs for the Sprint 10 AWS foundation.

Use it when any of these commands fail:

- `terraform fmt`,
- `terraform init`,
- `terraform validate`,
- `terraform plan`,
- `make terraform-validate`,
- `make terraform-plan-dev`,
- `make iac-scan`,
- GitHub Actions Terraform validation workflow.

Senior DevOps rule:

> A failed plan is useful feedback. Do not bypass it; classify it.

---

## 2. Safety rules

During failed-plan troubleshooting:

- do not run `terraform apply`,
- do not widen IAM permissions just to make a plan pass,
- do not commit real AWS account IDs,
- do not commit access keys, private emails, tokens, or real notification targets,
- do not suppress Checkov/TFLint findings without a documented reason,
- do not delete `.terraform.lock.hcl` unless you understand provider lock behavior.

---

## 3. Quick diagnosis flow

| Step | Question | Command |
|---|---|---|
| 1 | Am I in the repo root? | `pwd` |
| 2 | Does the environment exist? | `ls -la infra/environments/dev` |
| 3 | Are Terraform files formatted? | `terraform -chdir=infra/environments/dev fmt -recursive -check -diff` |
| 4 | Are providers initialized? | `terraform -chdir=infra/environments/dev init -backend=false -input=false` |
| 5 | Is the configuration valid? | `terraform -chdir=infra/environments/dev validate` |
| 6 | Does the dev plan run? | `terraform -chdir=infra/environments/dev plan -var-file=terraform.tfvars.example -no-color` |
| 7 | Do IaC scanners run? | `make iac-scan` |

Stop at the first failing step and classify the failure.

---

## 4. Standard local command sequence

From repository root:

```bash
mkdir -p ci-cd/reports/iac

terraform -chdir=infra/environments/dev fmt -recursive -check -diff
terraform -chdir=infra/environments/dev init -backend=false -input=false
terraform -chdir=infra/environments/dev validate
terraform -chdir=infra/environments/dev plan \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-plan-dev.txt
```

Expected result:

- `fmt` has no diff,
- `init` installs providers without backend access,
- `validate` returns `Success! The configuration is valid.`,
- `plan` shows the expected Sprint 10 baseline resources and no uncontrolled always-on services.

---

## 5. Failure classification

| Failure type | Typical symptom | Likely cause | Next action |
|---|---|---|---|
| Formatting failure | `terraform fmt -check` shows file diffs | Terraform style mismatch | Run `terraform fmt -recursive` and review diff. |
| Init failure | Provider cannot be installed | Network, provider version, lock file, registry issue | Re-run init, check `.terraform.lock.hcl`, check network. |
| Backend failure | Terraform tries to access remote state | Backend enabled too early or wrong command | Use `-backend=false` for Sprint 10 local validation. |
| Validate failure | Unknown variable/output/resource | Module interface mismatch | Fix module inputs/outputs. |
| Plan failure | Missing required variable | `terraform.tfvars.example` incomplete | Add safe example value. |
| Plan failure | AWS auth error | Credentials missing or expired | Refresh credentials only if real plan is intended. |
| Plan failure | Access denied | IAM plan role is too narrow or wrong identity | Review least privilege policy before changing access. |
| Scanner failure | Checkov/TFLint finding | Security or style issue | Fix or document a deliberate exception. |
| Tool path failure | Config file not found | Command run from wrong directory | Run from repo root or use absolute paths. |

---

## 6. Common Terraform errors

### 6.1. Missing provider initialization

Symptom:

```text
Error: Inconsistent dependency lock file
Error: Required plugins are not installed
```

Fix:

```bash
terraform -chdir=infra/environments/dev init -backend=false -input=false
```

Then re-run:

```bash
terraform -chdir=infra/environments/dev validate
```

---

### 6.2. Invalid module input

Symptom:

```text
Error: Unsupported argument
Error: Missing required argument
```

Diagnosis:

```bash
grep -R "variable \"" infra/modules/<module-name>
grep -R "module \"<module-name>\"" infra/environments/dev/main.tf
```

Fix:

- align the module call with `variables.tf`,
- add missing variables only when they are genuinely required,
- keep defaults safe and local-first where possible.

---

### 6.3. Invalid output reference

Symptom:

```text
Error: Unsupported attribute
Error: Reference to undeclared resource
```

Diagnosis:

```bash
grep -R "output \"" infra/modules/<module-name>
grep -R "module.<module-name>" infra/environments/dev/main.tf
```

Fix:

- check the output name,
- check whether the module creates the resource under the expected name,
- avoid exposing sensitive values in outputs.

---

### 6.4. Wrong var-file path

Symptom:

```text
Error: Failed to read variables file
```

Fix from repo root:

```bash
terraform -chdir=infra/environments/dev plan \
  -var-file=terraform.tfvars.example \
  -no-color
```

When using `-chdir`, the var-file path is relative to the target directory, not the repository root.

---

## 7. Common IaC scanner issues

### 7.1. TFLint config not found

Symptom:

```text
Failed to load TFLint config; failed to load file: open security/iac/tflint.hcl: no such file or directory
```

Most likely cause:

- command was run from a nested directory,
- `--recursive` scanned folders outside the intended Terraform scope,
- config path was relative to the wrong working directory.

Safer pattern from repository root:

```bash
ROOT="$(pwd)"
mkdir -p "$ROOT/ci-cd/reports/iac"

(
  cd "$ROOT/infra"
  tflint --recursive \
    --config "$ROOT/security/iac/tflint.hcl" \
    --format compact
) | tee "$ROOT/ci-cd/reports/iac/tflint.txt"
```

---

### 7.2. Checkov SSL or guidelines warning

Symptom:

```text
Failed to get the checkov mappings and guidelines
certificate verify failed
```

Interpretation:

- this can be a local certificate/tooling problem,
- it does not automatically mean the Terraform code is invalid,
- Checkov may still complete local Terraform scanning.

Next actions:

- save the report,
- review passed and failed checks,
- optionally re-run in GitHub Actions or a clean virtual environment,
- do not hide real failed checks behind a tooling warning.

---

### 7.3. Checkov finding requires architectural decision

Some findings are not simple syntax problems.

Examples:

| Finding | Possible interpretation |
|---|---|
| ECR should use KMS encryption | Stronger security baseline, but may require KMS scope and cost/management decision. |
| IAM policy uses `resources = ["*"]` | Some read/list/describe actions are not resource-scopeable; document why it is read-only and constrained by actions. |
| Public subnet assigns public IP | Usually avoid by default unless intentionally documented for public entry points. |

Fix the finding if it is clearly wrong. Document it if it is an intentional, reviewed exception.

---

## 8. Failed plan review checklist

Use this checklist before changing code:

- [ ] Did the failure happen in `fmt`, `init`, `validate`, `plan`, TFLint, or Checkov?
- [ ] Was the command run from the repository root?
- [ ] Was `-backend=false` used for local validation?
- [ ] Was the correct `terraform.tfvars.example` used?
- [ ] Are provider versions consistent with `.terraform.lock.hcl`?
- [ ] Did a module input/output change without updating the environment call?
- [ ] Did a security scanner find a real issue or a documented exception?
- [ ] Does the plan include NAT Gateway, EKS, RDS, OpenSearch, MSK, or other costly always-on services unexpectedly?
- [ ] Does any output expose a secret, account ID, email, token, or private identifier?

---

## 9. Evidence capture

For local troubleshooting evidence:

```bash
mkdir -p ci-cd/reports/iac

terraform -chdir=infra/environments/dev validate \
  -no-color | tee ci-cd/reports/iac/terraform-validate.txt

terraform -chdir=infra/environments/dev plan \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-plan-dev.txt

make iac-scan
```

Before committing evidence, review:

```bash
grep -R -E 'AKIA[0-9A-Z]{16}|arn:aws:iam::[0-9]{12}|[0-9]{12}' \
  ci-cd/reports/iac docs/runbooks infra \
  --exclude-dir=".terraform" || true
```

Expected result:

- no access keys,
- no real IAM account ARNs,
- no unexpected account IDs,
- no private notification values.

Note: `.terraform.lock.hcl` contains provider checksums. Those are not AWS account IDs or secrets.

---

## 10. Escalation criteria

Ask for senior review before continuing if:

- Terraform wants to destroy resources you do not recognize,
- IAM permissions need to be widened,
- a scanner finding requires disabling a security rule,
- a plan includes costly always-on services unexpectedly,
- the state file/backend behavior is unclear,
- real AWS resources exist but Terraform state is missing,
- output may contain sensitive data.

---

## 11. Resolution template

Use this template in PR notes or evidence docs.

```markdown
# Terraform Failed Plan Resolution — Sprint 10

Date:
Operator:
Branch:
Command that failed:

Failure category:
- fmt / init / validate / plan / tflint / checkov / credentials / backend / unknown

Root cause:

Fix applied:

Evidence files:

Security impact:

Cost impact:

Follow-up required:

Reviewer note:
```
