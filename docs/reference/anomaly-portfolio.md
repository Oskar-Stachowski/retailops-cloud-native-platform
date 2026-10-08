# AI07 bounded portfolio source profile 1.0.0

`ai-07-portfolio-v1` declares 128 business days, 8 products, 3 active selling
location/channel pairs and 2 stock locations, ending 2026-07-31. The potential
sales panel has 3,072 slots before lifecycle/assignment exclusions. Source seeds
are frozen to 42, 137 and 2026. Development tuning uses seed 42 and validation
only. Later windows of all three seeds are reserved for final evaluation.

This explicitly named bounded profile extends the 30-day transport fixture; it
does not claim to be the 365-day `ai-dev` or 730-day `ai-training`. The existing
offline whole-parent replay uses the explicit 2.1 binding with an 8,192 canonical
event limit for this profile. The unchanged 2.0 binding retains its 4,096 limit
for earlier profiles. Source
scenario qualification to 5,000 potential daily grains. Resource and event
counts must pass measured acceptance before this profile is qualified.

Zero-based windows are training 28–59, validation 64–95 and final test 100–127.
The gaps admit the sales/return availability delays. The first 28 days remain
available for causal history and cold-start coverage. Native source data also
retain the return tail. Every export uses the unchanged immutable snapshot03
protocol and typed Parquet, with date partitioning explicitly enabled.

The demand recipe places three instances of each demand type in each evaluation
window, on source-selected continuous series. Physical interventions use four
independent products, one return and one inventory episode in each window.
The source's paired counterfactual checks must prove real effects, commerce and
ledger reconciliation, and unchanged clean controls. No detector participates
in choosing source windows. The low number of physical episodes remains a
reported limitation; it must not be represented as a production qualification.

The profile's ordinary, preannounced promotion calendar adds seven-day campaigns
in validation and final test; they are normal controls, not business anomalies.
Normal/seasonal observations, promotions, demand shocks and inventory constraints
are reported separately. Injection labels and parameters remain in private
truth. Raw DQ faults are applied only to replay, with independent expected-action
reconciliation. No production ACK/DLQ durability is asserted here.

CLI generation uses `python -m data.anomalies.run_source --profile
ai-07-portfolio-v1 --seed 42 --portfolio demand` (or `physical`) with explicit
output storage and receipt paths. This document freezes preparation only;
AI07 ready requires downstream quality, lifecycle and serving acceptance.

## Explicit supply-adequate profile v2

`ai-07-portfolio-v2` keeps the same 128-day calendar, eight products, two stock
locations, seeds and temporal splits. It declares two selling pairs: store and
online at one physical selling location. Online has a continuous calendar;
store closures remain real exclusions. The potential sales panel is 2,048 slots.

V2 declares opening inventory 256, reorder point 128, safety stock 64 and minimum
order quantity 64. Supplier delays and the real inventory process remain active.
Ordinary base demand is multiplied by 0.75 before sampling, interventions and
facts. This is a whole-process profile setting, independent of truth labels,
evaluation windows and model decisions. It keeps the complete event census
inside the existing 8,192-event capture budget. Nothing is sampled or truncated.
V1 and legacy defaults remain unchanged.

The source comparison on v1 showed that ordinary supply exhaustion could mask
the demand interventions. V2 makes ordinary availability explicit so the five
intervention types can be evaluated against native observations. It remains a
small synthetic qualification profile, not `ai-training` or production evidence.

Generate each seed/scenario with `--profile ai-07-portfolio-v2`. Prepare parents
with `python scripts/data/prepare_ai07_portfolio.py --source SOURCE
--output-root data/generated/ai07-parents/CASE-SEED --bundle BUNDLE.json`.
Use a separate output root per case when running preparations concurrently:
the generated-directory guard also examines temporary files in its target.
The preparation verifies native source facts, typed partitioned snapshot03,
day coverage and the complete DQ fixture, including expected-action accounting.

## Confirmatory portfolio v3 (declared before new final scoring)

The v2 model experiment failed its unchanged numerical final quality gates.
Its final records remain `not_ready`. V3 is a separate synthetic qualification
scope, not a rerun or reinterpretation of the opened v2 holdout.

`ai-07-portfolio-v3` declares 128 days, **2026-01-01 through 2026-05-08**,
12 products, one selling location with store and online channels, and two stock
locations. Native stochastic rounding is unchanged. A uniform 0.50 factor on
base demand applies before sampling, intervention composition and commerce.
Opening stock 256, reorder point 128, safety stock 64 and minimum order 64
are unchanged from v2. The original 8192-event capture budget is unchanged;
no rows are sampled, trimmed or silently dropped.

The extra independent products increase the clean control cohort under the
unchanged conservative truth policy: all non-primary slots of intervened
products remain unknown after interventions. Windows, five intervention types,
magnitudes, neutral controls and required seeds 42/137/2026 are unchanged.
The new calendar produces different native random draws and facts. Results
qualify only this declared synthetic scope, not the prior v2 cohort or production.
Training and validation use seed 42, offsets 28–59 and 64–95. Final offsets
100–127 for all six seed/scenario cases remain unopened until model selection,
thresholds, metrics and complete public lineage are frozen.

## Separately reserved calibration cohort v4

The v3 final test failed precision and return-segment false-alert gates. Its
original models, frozen selections and failed results are retained.
`ai-07-portfolio-v4` declares the distinct 2025-01-01 through 2025-05-08 calendar
before any new final scoring. Dimensions, native demand factor, supply policy,
full-census 8192-event bound, five intervention types and magnitudes, conservative
truth mask, seeds and temporal offsets are identical to v3. No observations
are removed to improve measured quality.

This new synthetic cohort supports a separately declared event-capacity
calibration experiment. Development uses seed 42 only. Final windows of all
six cases are reserved until model versions and complete public lineages are
frozen. Repeated synthetic experiments are correlated; success would qualify
only this declared synthetic scope and would not validate v2, v3 or production.
