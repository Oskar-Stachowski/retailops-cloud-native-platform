# Prospective stockout stress profile

**AI 08 is READY (2026-10-05).** [Final acceptance](../evidence/ai/08/final/README.md)
records the completed six-world quality and actual serving acceptance. The design
and preregistered source interval below describe decisions made before final scoring.

`ai-stockout-stress-v1` is a separate, smaller qualified source proposal for AI 08
robustness. It defaults to 102 days, 30 products, three selling locations and two
physical stock locations. It requires an explicit end date and at least 84 days
to retain history, clean controls, stress and a mature tail. It does not replace
`ai-dev` or `ai-training`; previous profiles keep their numerical behavior.

The proposed final-source interval is **2026-06-09 through 2026-09-18**, on the
already preregistered seeds 42/137/2026. With this interval the existing planned
promotions begin around 13 July, after the current downstream selection cutoff.
This makes them observable in a later assessment, rather than only in training.
These dates were frozen before any final model outcome was scored.

`stockout-prospective-demand-shock-1.0.0` defines a seven-day latent-demand
increase beginning at zero-based day 49: **28 July through 3 August inclusive**
for this interval. Products are selected by SHA-256 of their identity modulo
three, with remainder zero. Their anomaly factor becomes 2, then returns to 1.
Membership and timing do not depend on targets, stockout labels or model scores.
Other products and times are clean controls. Natural planned promotions and
inventory constraints remain separately observable and may overlap; the final
campaign must freeze scenario definitions, support and overlap before scoring.

The factor enters the existing multiplicative latent-demand formula before
rounding, basket creation, fulfillment and ledger simulation. Observed sales,
lost sales, deliveries and stockout episodes are generated and reconciled from
that process. Labels and observed sales are never overwritten afterward. The
profile shares baseline `ai-load` catalog/location random draws; source identity
still binds the actual profile, dates, seed, table contents and code fingerprint.
The stress module is included in that fingerprint. Simulation factors are private
truth, and must never enter operational stockout features.

41 focused tests pass: 17 new stress cases and 24 existing source/intermittent
regressions, with no warnings. A real miniature 6-product × 84-day source passes
all 36 source checks. Its pre-shock arrivals and ledger exactly match a paired
baseline; the declared stress changes later demand and the resulting ledger.
This miniature proves source physics, **not model quality or portfolio readiness**.
Ruff/format pass for changed production files. Repository policy excludes data
tests from its broad ALL-mode lint; their format was separately checked.

The actual 30-product sources on seeds 42/137/2026 are prepared in
[run 37245910420](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37245910420),
using frozen producer `61eb215193106cc3f41e6b79e0470585cc9e791b` and consumer
`4faaf4b6c1997fda3a609645595165643bf302a9`. Generation, qualification/export/import,
sealed feature/label/upstream/temporal parents and resource receipts are complete.
The later test memberships are respectively 2627, 2609 and 2628; membership counts
are not model quality measurements. Exact source identities and ZIP SHA are
frozen in AI PR #14's six-world final campaign before outcome scoring.

The producer's full
[Required CI 37244283406](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/37244283406)
is successful, including data quality, AI03/AI06 cross-repo, API/Compose image/smoke
and security gates. This documentation update leaves the accepted producer code
and archived source contents intact; the final campaign retains its original
producer SHA. Source review/merge/main CI and the separately authorized independent model
evaluation are complete in the final acceptance. The original producer SHA remains
recorded in the frozen campaign. Profile design alone does not authorize a new promotion.
