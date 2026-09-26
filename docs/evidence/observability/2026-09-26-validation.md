# Observability validation — 2026-09-26

Step 6 passed real monitoring incident drills in GitHub Actions (AMD64) and
Jenkins (ARM64). Source head: `5b3fc7ab1dca68e63f3e3f3f91548adbaba51855`. GitHub tested PR merge `ef9b5974f3b360e3f7ff996363727ad54cfa0a64`;
both commits and implementation merge `7188d813dac0023a5daa99b7aa0210b3f823641a` have Git tree `e606760f74d8ab98585fada612f649d0281dc5d4`.
The [machine-readable snapshot](2026-09-26-validation.json) retains rule states,
metric/query evidence, image identities, report hashes and all required job results.

## Executed checks

| Check | Result |
|---|---|
| API and Prometheus targets | Both individually healthy, with real ingested API, DB and stream samples |
| Grafana | Four provisioned dashboards and live Prometheus datasource queries before/after the incident |
| Fault | Stopped only the randomly named disposable stack's API |
| Alert | `RetailOpsApiMetricsTargetDown`: inactive → pending → firing → inactive |
| Hold threshold | Original `for: 2m`, unchanged for the drill |
| Stop to observed firing | GitHub **150.61 s**, Jenkins **198.29 s**; includes scrape/evaluation scheduling |
| Five-minute scrape ratio | 1 before the incident; GitHub 0.1818, Jenkins 0.1538 at firing |
| Recovery | Same API container restarted without migrations/seed dependencies; scrape and Grafana query recovered |
| Cleanup | Owned containers, volumes and network removed; existing developer containers preserved |
| Wider GitHub gates | **24/24 Required CI jobs passed**, including 7 Chromium journeys, recovery/rollback and local Kubernetes |
| Focused validation | Observability CI: **32 tests passed** and promtool config/rule/transition checks; local focused selection: 21 passed |

Execution: `make compose-ci`. Source directories were clean in both runtime
reports. The reduced rolling ratio during the injected fault is expected and
is not a normal-availability measurement. Full 30-day observation is absent.

[Required CI run](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36251803830),
[Observability CI run](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36250641792),
[actual Jenkins execution](../jenkins/2026-09-26-validation.md).
The downloaded GitHub artifact ZIP hashes were verified against artifact metadata.
The 32-test Observability CI run used `41d19a3`; its monitoring code and tests are
unchanged in the final source revision (only Jenkins checkout metadata changed).

## Operational changes and limits

The smoke check now rejects an unhealthy API even when Prometheus itself is up,
and waits for the initial scrapes. The drill also waits for the first successful
rule evaluation. Regression tests cover those startup conditions, refusal to
inject faults into unowned projects, cleanup after failure and preservation of
the GitHub browser gate. CI and Jenkins use unique projects, loopback ports,
images and volumes; neither tears down the default development stack.

The [initial SLO definition](../../observability/slo.md) is 99.9% successful
API metric scrapes over 30 days, with explicit sample coverage and monitoring-gap
requirements. This short run proves signal mechanics, not production or
30-day compliance. There is no Alertmanager/notification receiver; no external
notification was sent. Request-level SLOs, centralized logs and end-to-end
tracing remain separate work. Existing historical screenshots were preserved.
