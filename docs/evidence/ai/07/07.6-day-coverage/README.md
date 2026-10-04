# AI07.6 — explicit scoped event-day closure declarations

Producer acceptance passed on 2026-10-04, Python 3.11.15 / Darwin ARM64. This
additive slice follows full raw-DQ v2 in PR #83. AI07 remains open. The
[contract guide](../../../../reference/business-day-coverage.md) defines the exact
scope and the [machine receipt](verification.json) records tested identities and hashes.

Both sources were independently reconstructed with their original source IDs.
The operational declaration contains 678 sales-day rows per profile. Assortment
exclusions are absent grains, not synthetic zeros. The publisher explicitly declares
return event days for purchases in this finite parent, including the native tail.
Sales completeness, closed locations and missing source observations are distinct.
Every declaration has an exclusive UTC day end, `known_at`, expected native IDs
and, for returns, required original purchase IDs.

| Case | Total declared days | Coverage ID suffix |
| --- | ---: | --- |
| Demand | 1713 | `2a1102d5068df76ee276eadea3e9afdf772703b915c16f4e00373ba2af0d5aef` |
| Physical | 1717 | `cd82a5392012a8ec57a7b73301f6c579034f95f40b29f484834d5888e17444d5` |

All 17 targeted tests pass. Two fresh processes each generated and verified both
profiles, with identical source IDs, coverage IDs, payloads and all three artifact
checksums. Measured process times were 131.795 / 151.108 seconds, with peak RSS
210.453 / 213.062 MiB, below 300 seconds / 1024 MiB. Source bytes stayed unchanged.
Ruff, formatting, configured Mypy, high/high Bandit and Actionlint pass.

Required Data CI appends this proof to the existing AI07 job. Its general data-test
timeout increases from 30 to 35 minutes to accommodate the new native-parent tests
(local targeted run: 236.40 seconds). Every earlier gate and per-process limit stays
enabled. Final-head CI results are recorded in the PR. Local `make ci-local` ran:
682 API tests passed, 57 DB-dependent tests skipped and four failed with the local
Docker daemon unavailable. Coverage collection also found mixed branch / statement
data; CI explicitly supplies `--cov-branch`. The remaining frontend tests, lint and
build passed separately. The local Docker daemon was left untouched. Full container
and database acceptance must pass on the isolated required-CI runner.

The archive exported to the independent consumer contains only these public
declarations. The declaration policy does not use private truth, cohort flags,
transport progress or maximum event time. It does not establish global returns,
carry-in purchases or broker durability. The consumer still must independently
verify the closure and its accepted delivery-time facts before using a value.
Residual features, detector comparison, evaluation and anomaly lifecycle remain open.
