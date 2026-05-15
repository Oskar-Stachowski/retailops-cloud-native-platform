# RetailOps data contracts

This folder contains the portfolio-level data contracts for the synthetic RetailOps dataset.

The contract is intentionally lightweight and repository-native: it validates the CSV files that are used by the demo seed process before those files are loaded into PostgreSQL. It does not replace database constraints or Pydantic API schemas; it adds a data-layer gate between the generator and the database.

## Contracts

| File | Purpose |
| --- | --- |
| `retailops_seed_dataset.contract.json` | Required CSV files, required columns, seeded DB tables, quality-report expectation and required business scenarios. |

## Local validation

From the repository root:

```bash
make data-generate
make data-contracts
make data-scenario-report
```

Expected evidence:

- `ci-cd/reports/data/data-contract-report.json`
- `ci-cd/reports/data/scenario-coverage-report.json`
- `docs/evidence/data/scenario-coverage-report.md`

## Claim boundary

Safe claim after the gates pass:

> Synthetic retail data is generated deterministically, validated against repository-owned data contracts, and loaded into PostgreSQL through the same seed path used by local/CI integration tests.

Careful claim:

> The contracts are repository-native JSON contracts, not a full enterprise data catalog or Great Expectations deployment.
