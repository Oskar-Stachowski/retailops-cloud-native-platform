## Summary

Describe the change and the main reason for it.

## Validation

- [ ] `make ci-local`
- [ ] `make compose-ci` when Docker/runtime behavior changed
- [ ] targeted tests or workflow-specific commands were run
- [ ] docs or evidence were updated when behavior or reviewer-facing claims changed

## CI / DevSecOps Impact

- [ ] no CI workflow changed
- [ ] CI workflow changed and `actionlint` or equivalent YAML validation was run
- [ ] required check names are still compatible with `docs/governance/branch-protection.md`
- [ ] artifact paths still write to `ci-cd/reports/**`
- [ ] `continue-on-error`, `soft-fail`, and `if-no-files-found` choices are intentional

## Evidence Checklist

- [ ] implementation status remains accurate
- [ ] screenshots or snapshots were refreshed if stale
- [ ] new reports or artifacts are sanitized before tracking in Git
- [ ] follow-up risks or known gaps are documented

## Reviewer Notes

List the main files or areas that need focused review.
