# AI07.2 — raw DQ faults and bounded offline replay

Status: **local acceptance passed**, separate PR candidate. This completes the
eight raw fault scenarios and the bounded selected-sales portion of 07.3. **AI07
as a whole is not ready.** AI03 publication, anomaly features/detectors, evaluation
and AI05 lifecycle integration remain outstanding. Business scenario work is in
the independent PR #78.

Runtime commit: `0a39ab43f462e7d5bea24854a22f29816b16c6d3`.
Evidence was generated from clean implementation/dependency provenance.
See [verification.json](verification.json) for full hashes, CLI commands and source
file integrity, and [the reference](../../../../reference/raw-dq-replay.md) for the
contract, policies and reproduction steps.

## Acceptance

The physical CLI run creates a source 2.7 `ai-smoke` dataset with seed 42, 14 days,
8 products, 3 stores and 2 warehouses. All 58 tables and all 36 source gates pass.
Two fresh output directories produce the same fixture ID and byte-identical
contents of all seven package files. A separate CLI verification requires the
original parent and reconstructs every generated artifact. Checksums of every
source file are identical before and after the DQ runs.

Fixture ID:
`raw-dq-sha256-d627a72189498acc75c94d03627c501e177049b3ff2dfdd152c5a691fc99c6cb`.

| Result | Count |
|---|---:|
| Selected canonical sales | 256 |
| Raw event deliveries | 258 |
| Accepted facts / aggregate revisions | 253 |
| Exact duplicates | 1 |
| Business duplicates | 1 |
| Quarantined / offline DLQ references | 3 |
| Accepted late events | 1 |
| Accepted out-of-order events | 1 |
| Explicit progress declarations | 14 |
| Reconciled injections | 8 / 8 |

The missing optional `sku` case is accepted with unchanged business semantics.
Unsupported `2.0`, unsupported `1.1` and an additive unknown payload field are
quarantined under the unchanged legacy contract. The injection prevalence is
8/256 = 3.125%, within the recommended range for this bounded fixture.

The final declared frontier is `2026-07-31T23:59:59.999999+00:00`; the maximum
accepted event time is separately `2026-07-31T09:01:10+00:00`. This fixture makes no
claim of complete curated business data: `curated_completeness=not_qualified`.

## Validation

- 59 new raw DQ tests plus 22 source regression tests: **81 passed**.
- Legacy contract, consumer, quarantine and generator CLI regressions: **72 passed**.
- Total local tests: **153 passed**.
- Ruff check passed; all 230 production files passed format checks.
- Mypy passed for all eight new modules; diff hygiene passed.

Negative coverage includes ambiguous plans/anchors, wrong source binding,
unsupported schemas, truth fields, invalid money and quantity, malformed JSON,
duplicate JSON keys, unavailable facts, event/business conflicts, offset rewrites,
regressing progress, invalid capture metadata and tampered raw identities. The
independent reader also rejects self-resealed package mutations, extra files,
symlinks and an attempted upgrade of the completeness claim.

Temporal tests prove that a late fact appends a revision to an existing aggregate
and retains its predecessor; queries at the prior cutoff remain byte-equivalent.
Replaying the same capture changes neither counts, accepted facts nor revisions.

## Limits and integration

There is no broker, DB or shared service mutation in this work. The DLQ is a local
reference fixture, with no claim about delivery/ACK/durability (AI10). The parent
and fixture are bounded, sampled operational sales; no stock or return read model
is published. The reader never receives private injection labels. Source and model
handoff readiness stay false. No AI05 session files, processes or services were
changed.

Remote Required CI status is recorded on the PR for its exact head commit.
