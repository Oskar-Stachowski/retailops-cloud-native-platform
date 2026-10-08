# AI07.5 — full producer-side sales and native return replay

Local acceptance passed on 2026-10-03, runtime
`ae1178ccfc7f3019645a364acb4ca210f8a05c95`, Python 3.11.15 / Darwin ARM64.
This draft follows the source 2.8 handoff in PR #80. It replaces sampling only
through an explicit additional v2 entry point; selected-sales v1 remains available.
AI07 as a whole is not ready. See the [contract and reproduction guide](../../../../reference/full-raw-dq-replay.md)
and [machine verification](verification.json) for commands, identities and checksums.

## Full source coverage and faults

Each 30-day source has 8 products, 3 stores and 2 warehouses, seed 42, and passes
the source 2.8 process / commerce / inventory gates. The full projection includes
every canonical sale and native return claim, including the post-history tail.
Rejected claims remain separate from refunded units; original native locations
and currency are resolved from the verified purchase, not the legacy wire store.

| Case | Canonical sales | Native return claims | Canonical total | Delivered events | Accepted facts | Quarantined / missing |
|---|---:|---:|---:|---:|---:|---:|
| Demand | 1401 | 232 | 1633 | 1637 | 1627 | 6 |
| Physical | 1390 | 246 | 1636 | 1640 | 1630 | 6 |

Both cases reconcile all eight faults on each wire type: 16 injections, two exact
duplicates, two business duplicates, two late and two out-of-order arrivals.
Missing optional context preserves business semantics; unsupported versions and
additive fields go to quarantine with offline DLQ references. Coverage identifies
the six missing canonical facts per native grain. Revisions retain predecessor,
raw reference and arrival-time knowledge; earlier as-of views remain unchanged.

## Reproduction and resource budget

Four complete fresh processes generate source, build / verify full replay,
reuse the immutable fixture and check every original source byte for mutation.
Repeat runs have identical source / fixture IDs, all source artifact checksums
and all seven publication file checksums. Source manifest semantics match after
excluding only its wall-clock `generated_at`; actual timestamps and manifest
checksums are retained, and each manifest stays immutable within its run.

| Case | First / repeat seconds | First / repeat peak RSS MiB |
|---|---|---|
| Demand | 123.59 / 139.58 | 237.61 / 210.56 |
| Physical | 157.48 / 132.27 | 186.67 / 234.45 |

Each process meets 300 seconds / 1024 MiB. The largest replay artifact is below
the explicit 32 MiB limit. Required Data CI runs the same four-process acceptance
on Linux with Python 3.11.15. Its final-head result is recorded on the draft PR.

## Validation

All **48 full-DQ tests** passed on the frozen runtime; **896 existing data
regressions** and **72 legacy contract / consumer / quarantine / CLI tests**
also passed. The initial 942-case data run overlapped a checker edit, and one
immutable-package fingerprint test correctly rejected the changed implementation.
The subsequent frozen 48-case run includes that test and two added malformed
envelope cases: 944 unique data checks are verified with no unresolved failure.

Ruff, formatting of 251 production files, configured Mypy, Actionlint, high/high
Bandit, 16 CI detection checks and 11 immutable-input checks passed. Directory
and all-ref Gitleaks scans found no leaks. Negative tests cover wrong parent
quantities / money / routes / clocks / event identities, private payload fields,
malformed and nonfinite JSON, missing coverage, capture version / offset / clock
guards, overlap and partial-stream plans, and self-resealed false aggregates.

## Remaining boundary

This is a producer-side offline fixture and replay, not independent AI acceptance.
The additive schema files change implementation-bound source identities; fresh
source 2.8 is generated for this proof and earlier frozen artifacts are untouched.
AI intake must bind these new source IDs through its own verified handoff.

Full parent-fact coverage is not business event-day closure. Missing grains stay
unknown, aggregate evidence remains partial, and business completeness / model
readiness remain unqualified. A separate reviewed operational event-day coverage
policy is required before dense zero-valued observations or model qualification.
Baseline / Isolation Forest, evaluation and anomaly lifecycle remain open.
Broker durability, ACK and live DLQ are AI10 work. No AI05 checkout, process,
service, volume or serving input was modified.
