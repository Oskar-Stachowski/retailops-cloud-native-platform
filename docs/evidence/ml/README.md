# ML Evidence

This folder contains curated, commit-ready evidence for local RetailOps MLOps
workflows.

## Contents

| Path | Purpose |
| --- | --- |
| [random-forest-v1](random-forest-v1/README.md) | Latest retained model artifact; its evaluation has known limitations and requires reassessment before qualification. |
| [experiment-identity-2026-09-27.md](experiment-identity-2026-09-27.md) | Bounded 20/80-tree and repeat-run identity verification; no model qualification. |

These files are reviewer-facing evidence with their original execution dates.
Raw CI output remains under ignored `ci-cd/reports/`. The `small` dataset is
versioned; larger generated datasets are ignored. See [data profiles](../../reference/data-profiles.md).
