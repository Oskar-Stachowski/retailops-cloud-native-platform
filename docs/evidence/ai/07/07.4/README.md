# AI07.4 — anomaly source/snapshot handoff

Status: **local transport/import acceptance passed**, separate draft PR candidate.
AI07 as a whole remains open. This slice combines the business scenario and raw
DQ preparation in PRs #78/#79, introduces source **2.8.0** and snapshot **1.2.0**,
and proves an independent AI wheel import. The branch contains both upstream
preparation PRs until those dependencies land on main.

Runtime commit: `b59aca8e2fe70a76efde2192b63b5bf839104bac`.
See [verification.json](verification.json) for every source/snapshot identity,
file checksum, recorded code/dependency provenance and consumer receipt, and
[the reference](../../../../reference/anomaly-source-handoff.md) for reproduction.
All recorded runtime file hashes match the current implementation. Source/DQ
provenance records clean runtime code. No AI05 checkout, process or service changed.

## Physical acceptance

The two independently scoped sources use seed 42, 30 days, 8 products, 3 stores
and 2 warehouses. Both retain **58 source tables** and pass **38 hard gates**.
Demand covers one-day spike, multi-day spike and sustained drop; physical covers
real return spike and inventory censoring. The source CLI verifies each immutable
parent in a separate process and regenerates its tables and private effects.

| Source | Public rows / tables | Private rows / tables | Build/export/DQ time | Peak RSS |
|---|---:|---:|---:|---:|
| Demand | 13,625 / 43 | 22,099 / 55 | 237.16 s | 204.47 MiB |
| Physical | 13,603 / 43 | 21,983 / 55 | 230.37 s | 212.81 MiB |

Each source has a separate eight-fault DQ package: 256 selected canonical sales,
258 raw deliveries, 253 accepted facts/revisions, one exact duplicate, one
business duplicate, three quarantine/offline DLQ entries, one accepted late
event and one accepted out-of-order event. All eight injection actions reconcile.
The canonical source files remain unchanged. Selected-stream progress is explicit;
full curated completeness and transport durability remain unqualified.

Public and private exports use separate immutable directories and identities.
Private plans/effects/configuration are confined to explicit evaluation artifacts.
Two fresh installed-wheel processes each import, reimport and verify all four
variants with identical source/snapshot IDs and unchanged input/publication files.
The producer module is unavailable in those processes. Each case takes 9.68–16.67
seconds; the acceptance limits are 300 seconds and 1024 MiB per case.

## Validation and next boundary

- 55 producer source/snapshot tests passed, including 10 new anomaly tests.
- 94 consumer regression tests and 8 new anomaly import tests passed.
- Producer Ruff and targeted Mypy (five new/modified handoff modules) passed.
- Consumer Ruff/format and full Mypy (193 modules) passed; wheel build/install passed.

Negative tests reject extra truth files, missing opt-in, private plan binding
changes even after artifact resealing, unknown versions and source truth-only
changes even after checksum resealing. Existing source 2.7/snapshot 1.1 transport
regressions remain green. Chunking/republication preserve snapshot identity.

This is a transport boundary. Curated anomaly support, DQ integration into that
consumer path, historical expected/residual/scale features, baseline/Isolation
Forest, observation/episode evaluation and AI05 MLflow/serving integration remain
outstanding. Existing forecasts are not requalified by this handoff. Broker
durability and RetailOps read models remain AI10. Exact-head remote CI is linked
on the PR, separately from this local artifact evidence.
