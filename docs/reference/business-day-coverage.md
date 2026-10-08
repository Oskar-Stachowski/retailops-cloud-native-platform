# Business event-day coverage 1.0

AI07 publishes an additive closure artifact from a verified source 2.8. It leaves
the source 2.8, snapshot 1.2 and sales/returns transport 1.0 schemas unchanged.
The package owns its schema registry under `data/day_coverage/contracts` so it does
not alter the source or existing full-DQ code fingerprints.

```sh
python -m data.day_coverage.run build --source SOURCE --output-root COVERAGE_ROOT
python -m data.day_coverage.run verify --source SOURCE --directory COVERAGE
```

The exact three-file artifact contains canonical `days.jsonl`, a content-addressed
`coverage_manifest.json`, and its SHA256 seal. The descriptor binds the source ID,
five public native table identities, publisher policy, code, dependencies and
Python version. Verification reconstructs every declaration against the independently
verified native source. It does not accept a resealed false count, zero or timestamp.

The grain is `(event_type, business_date, product_id, selling_location_id, channel,
currency)`, using UTC event days. Sales require the explicit daily observation's
`source_data_complete` and valid quality status. Closed locations and missing
observations remain separate states. `known_at` is at least the exclusive day end,
observation availability and native sale availability. The observation's final
quantity is used to validate the declaration, never to populate a historical AI value.

Returns use the publisher's explicit assertion for a **verified complete synthetic
export and bounded native ingestion**, scoped to `purchases_in_parent_source_only`.
Each purchased series is declared from the source start through its last purchase
date plus the applicable return window. The closure becomes available after the
exclusive event-day end plus the policy's ingestion delay, and after the first
purchase and policy become known. Expected claim IDs include native refunded and
rejected claims. Required sale IDs identify all purchases in that series before the
day end. This permits an independent consumer to withhold a zero when a purchase
receipt is missing. Absent series and dates outside the declared interval are unknown.

This assertion is specific to this finite synthetic publisher. It is not evidence
of global return coverage, carry-in purchases, Kafka acknowledgements or closure of
a production source. Purchase-cohort maturity, progress records and maximum event
time do not establish event-day closure. No cohort flag, scenario label or private
simulation table enters the projection. The consumer must independently check these
declarations and its delivery-time DQ state before using a value in scoring.

Bounds: 10,000 declaration rows, 32 MiB payload, existing DQ parent limits of 5,000
daily source grains and 64 MiB source artifacts. Each fresh acceptance process covers
both profiles within 300 seconds and 1024 MiB. Run `python
scripts/data/check_day_coverage.py --output RECEIPT.json` for two-process acceptance.
The existing Data CI AI07 job executes it without skipping any earlier gate.
