# Jenkins execution — 2026-09-26

Actual Jenkins Pipeline build **4** finished **SUCCESS** using the repository's
`Jenkinsfile` at `5b3fc7ab1dca68e63f3e3f3f91548adbaba51855`. It started at
`2026-09-26T15:24:52.014000+00:00` and took **624.717 seconds**.
The [JSON snapshot](2026-09-26-validation.json) contains stage results from the
Jenkins REST API, artifact paths/SHA-256 hashes, controller/plugin versions and
the archived pipeline summary.

## Environment and stages

Jenkins **2.555.1** ran as a separate authenticated, loopback-only controller with
a temporary home and one native macOS ARM64 executor. Installed plugin binaries
were copied into that temporary home; the existing Jenkins job/home was not used.
The job checked out the public GitHub repository through SCM. The controller was
stopped after collecting evidence. It is not a permanently running CI service.

| Stage | Result |
|---|---|
| Checkout and toolchain | SUCCESS; exact source SHA recorded |
| Install Dependencies | SUCCESS |
| Data Quality Gate | SUCCESS, profile `small` |
| Local CI Gate | SUCCESS; **271 backend tests passed, 40 skipped, 76% coverage**; frontend tests/lint/build and data contracts/scenarios passed |
| Isolated Build, Runtime and Alert Drill | SUCCESS; API/frontend HTTP, streaming, monitoring, real outage and recovery |
| Archive artifacts | SUCCESS; 8 allowlisted artifacts, fingerprinting enabled |

The earlier first-build attempt exposed missing shell parameter initialization;
a later attempt exposed the initial rule-evaluation timing assumption. Archive
review also found a missing SHA in the short summary after build 3;
this final run explicitly records the checked-out commit, matching both runtime
reports. Those issues were fixed and checked before this successful run. Failed
runtime runs also executed scoped cleanup. No earlier failed build is represented as success.

See the [monitoring evidence](../observability/2026-09-26-validation.md) for the
198.29-second stop-to-firing observation, complete alert transition and recovered
Grafana query. GitHub tested a synthetic PR merge with the **same Git tree** and
passed all 24 Required CI jobs, including seven browser journeys. Browser tests
were not enabled in this Jenkins build. Broader security and cloud/registry
validation remain separate GitHub workflows; Jenkins performs no deployment.

## Repeat

Use **Pipeline script from SCM**, this repository, `Jenkinsfile`, a trusted
revision and `DATA_PROFILE=small` on an agent with Git, Make, Python 3.11,
Node/npm and Docker Compose. Record the actual checkout SHA and final build API
result. Review the archived commit summary, `isolated-runtime.json` and
`incident-drill.json`; require `passed`, clean source and successful cleanup.
Full setup and ownership are in [the CI/CD guide](../../../ci-cd/README.md).

The two older PNG screenshots remain unchanged as historical material. This
snapshot is dated execution evidence, not a screenshot refresh or proof of a
production Jenkins service, production SLO compliance or alert delivery.
