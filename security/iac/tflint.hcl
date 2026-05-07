# RetailOps IaC TFLint configuration
#
# Sprint 10 policy:
# - TFLint is a hard quality gate in CI.
# - The goal is fast feedback on Terraform quality before adding AWS apply automation.
# - Provider-specific enterprise hardening remains a later sprint concern.

config {
  call_module_type = "local"
}

rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}

rule "terraform_unused_declarations" {
  enabled = true
}

rule "terraform_deprecated_interpolation" {
  enabled = true
}

rule "terraform_deprecated_index" {
  enabled = true
}

rule "terraform_typed_variables" {
  enabled = true
}

# Documentation rules are useful, but not yet a blocking gate for Sprint 10.
# We already keep module README files and will tighten variable documentation later.
rule "terraform_documented_variables" {
  enabled = false
}

rule "terraform_documented_outputs" {
  enabled = false
}
