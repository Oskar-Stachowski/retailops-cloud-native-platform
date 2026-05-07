# RetailOps Synthetic Data Operating Model

## 1. Purpose

This document defines how RetailOps synthetic datasets should be generated,
validated, reviewed and used across local development, CI, Jenkins, future AWS
data lake work, observability and MLOps.

It complements:

- [Synthetic Data Profiles](synthetic-data-profiles.md)
- [Data README](../data/README.md)
- [CI/CD README](../ci-cd/README.md)

## 2. Operating Principles

RetailOps synthetic data has three responsibilities:

- provide a fast deterministic seed for API and dashboard tests,
- provide realistic enough operational data for platform and observability work,
- provide controlled data signals for early MLOps and analytics experiments.

The generator should stay deterministic:

```text
same profile + same parameters + same seed -> same dataset
```

Generated heavy datasets should not be committed. Only the small `demo` seed and
generator code should be versioned.

## 3. Profile Usage Policy

| Profile | Use by default | Main use | CI policy | Storage |
| --- | --- | --- | --- | --- |
| `demo` | API seed and contract tests | Fast local app seed | API CI | committed under `data/demo` |
| `small` | Developer and PR data quality gate | Realistic local validation | default Data CI and `make data-quality` | ignored under `data/synthetic/small` or `ci-cd/reports/data` |
| `medium` | Manual or release validation | Platform, observability, first MLOps checks | manual GitHub Actions / Jenkins parameter | ignored local generated data |
| `large` | Future data lake/performance evidence | S3/Parquet scale validation | not a default CI gate | object storage only |

Decision rules:

- Use `demo` when validating API seed compatibility.
- Use `small` for PR quality gates and local generator work.
- Use `medium` before claiming platform/MLOps readiness.
- Do not use `large` until Parquet/S3 output and cost controls exist.

## 4. Standard Commands

Generate the committed demo seed:

```bash
python3 -m data.generator.main
```

Generate local `small`:

```bash
python3 -m data.generator.main --profile small
```

Generate a bounded profile for testing:

```bash
python3 -m data.generator.main \
  --profile small \
  --days 14 \
  --products 20 \
  --stores 4 \
  --warehouses 3 \
  --output-dir /private/tmp/retailops-quality-check
```

Run the local quality gate:

```bash
make data-quality
```

Run a medium validation manually:

```bash
make data-quality DATA_PROFILE=medium
```

## 5. Generated Artifacts

Every generated profile writes:

```text
dataset_manifest.json
quality_report.json
```

Non-demo profiles also write:

```text
realism_report.json
```

Artifact responsibilities:

| Artifact | Purpose |
| --- | --- |
| `dataset_manifest.json` | Dataset identity, profile, parameters, row counts, date range and artifact list. |
| `quality_report.json` | Structural quality gate: FK consistency, non-negative values, order totals, date windows and known data quality statuses. |
| `realism_report.json` | Business realism evidence: long-tail, average basket size, promo uplift, stockout rate, returns and data quality issue distribution. |

The quality gate should fail when:

```text
quality_report.json.status != passed
```

## 6. CI and Jenkins Model

GitHub Actions:

- `.github/workflows/data-ci.yml` runs `make data-quality`.
- Default profile is `small`.
- Manual dispatch can run `small` or `medium`.
- Reports are uploaded as workflow artifacts.

Jenkins:

- Jenkinsfile has a `DATA_PROFILE` parameter.
- `Data Quality Gate` runs `make data-quality DATA_PROFILE="${DATA_PROFILE}"`.
- Existing artifact archiving captures `ci-cd/reports/**`.

Local preflight:

- `make ci-local` includes `make data-quality`.
- Developers can run `make data-quality` directly when working only on data.

## 7. Review Checklist

Before accepting a synthetic data change, review:

- `quality_report.json.status` is `passed`.
- `dataset_manifest.json.row_counts` match expected profile scale.
- `realism_report.json` looks plausible for non-demo profiles.
- `top_20_percent_product_revenue_share` is not too flat or too extreme.
- `average_order_items` is above 1 for synthetic profiles.
- `promotion_uplift_ratio` is positive but not perfect.
- `stockout_rate` is non-zero but not dominant.
- category returns are plausible.
- controlled data quality issues exist but remain low.
- generated heavy files are not staged for commit.

Current accepted `small`/`medium` realism ranges:

| Metric | Desired range |
| --- | ---: |
| top 20% product revenue share | 0.60-0.85 |
| average order items | 1.3-3.5 |
| promotion uplift ratio | 1.10-1.80 |
| stockout rate | 0.01-0.10 |
| controlled data quality issue rate | 0.005-0.05 |

## 8. Git Policy

Commit:

- generator code,
- tests,
- documentation,
- `data/demo` CSV seed and demo reports.

Do not commit:

- `data/synthetic/`,
- `data/generated/`,
- `data/replay/`,
- `ci-cd/reports/` generated outputs,
- large CSV/Parquet/JSONL outputs,
- local one-off validation directories.

The `.gitignore` should keep generated synthetic datasets out of Git.

## 9. AWS and MLOps Readiness

Before using generated data for AWS data lake or MLOps evidence:

- run `make data-quality DATA_PROFILE=medium`,
- inspect `realism_report.json`,
- confirm storage size and runtime are acceptable,
- prefer Parquet/S3 once profile size exceeds comfortable CSV handling,
- keep generated AWS datasets out of Git,
- record manifest and quality reports as evidence.

For `large`, require these prerequisites first:

- Parquet writer,
- partitioning strategy,
- S3 lifecycle policy,
- cost assumptions,
- cleanup runbook,
- quality and realism validation gate.

## 10. Troubleshooting

Quality report failed:

- open `quality_report.json`,
- find checks with `"status": "failed"`,
- inspect the check details,
- fix generator logic before regenerating.

Realism report looks implausible:

- check long-tail concentration,
- check return rates per category,
- check promotion uplift,
- check stockout rate,
- recalibrate realism layer constants or demand classes.

Generated files show up in Git:

- confirm the path is under `data/synthetic/`, `data/generated/`,
  `data/replay/` or `ci-cd/reports/`,
- update `.gitignore` if a new generated path was introduced,
- do not commit large generated outputs.

Generator is slow:

- reduce `--days`, `--products`, `--stores`, or `--warehouses`,
- use `small` for local iteration,
- reserve `medium` for manual validation,
- wait for Parquet/chunked writer before using `large`.

