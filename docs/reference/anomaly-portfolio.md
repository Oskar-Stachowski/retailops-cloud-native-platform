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
