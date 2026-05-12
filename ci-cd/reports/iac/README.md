# IaC Report Snapshots

This directory contains raw or semi-raw Infrastructure-as-Code outputs.

The tracked `sprint-10-*` files are sanitized snapshots from a controlled Terraform AWS showcase. They are intentionally separated from `docs/evidence/aws/`, which stores screenshots and human-readable cleanup notes.

## Tracked Files

| File | Purpose | Sanitization note |
|---|---|---|
| `sprint-10-terraform-validate.txt` | Terraform validation result. | No sensitive values. |
| `sprint-10-terraform-plan-dev.txt` | Terraform plan summary for the dev foundation. | Full raw resource identifiers are not included. |
| `sprint-10-terraform-apply.txt` | Terraform apply summary from the temporary AWS showcase. | Account IDs, ARNs, resource IDs, console URLs, and private notification data are excluded. |
| `sprint-10-terraform-destroy.txt` | Terraform destroy summary proving cleanup. | Account-specific identifiers are excluded. |

## Ignored Local Outputs

Local files such as `checkov.*`, `tflint.txt`, `terraform-plan-dev.txt`, `terraform-validate.txt`, and commit-specific plan exports are ignored by default. Convert them to sanitized snapshots before tracking them.
