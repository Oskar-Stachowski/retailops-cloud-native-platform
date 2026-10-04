# AI 10: authenticated shared broker acceptance runtime

This is an independent, disposable **output transport** stack. It connects the
actual pinned AI outbox worker to the source checkpoint consumer and HTTP API.
It uses separate PostgreSQL servers, databases, credentials and database networks,
and one private Redpanda broker with verified TLS, SCRAM-SHA-256 and literal ACLs.
It does not join either repository's running Compose project or expose host ports.

## Scope of the evidence

The AI input is the owner's explicitly named `retailops-demand-forecast-v12-mechanics`
fixture. The AI output parent table is a storage double; the actual pinned `0020`
outbox migration and unchanged delivery CLI run against PostgreSQL. Source migrations,
checkpoint/fencing, projection, bearer authentication and HTTP reads are real.
No model runs, MLflow approvals, active production head or promotion are generated.
This drill does not establish full AI database/publication integration, anomaly or
stockout transport, snapshot/replay, source completeness, UI or 102-day three-model E2E.

## Run step by step

1. Use a clean checkout/worktree of this source branch. Read
   `scripts/intelligence-runtime/owner.json` and obtain the exact AI commit
   `3a64b03ac707a7bc041bef4ad80e451c9ff8e49a` in a separate checkout/worktree.
   Leave AI 07/08 checkouts, model environments and running sessions untouched.
2. Validate without starting Docker or any container:

   ```sh
   python3 scripts/intelligence-runtime/drill.py \
     --owner-root /absolute/path/to/pinned-ai-worktree --verify-config
   ```

   The controller verifies the AI commit, tracked tree, owner/client pin and SHA-256
   of both delivery lock/config and main ML lock, worker and fixture. It creates
   temporary secrets, validates resolved Compose boundaries, then removes them.
   Python 3.11+ and OpenSSL are required; Compose must support additional build contexts.
3. Use an isolated CI runner with Docker already running. The controller never
   starts a stopped daemon. For the actual acceptance drill run:

   ```sh
   python3 scripts/intelligence-runtime/drill.py \
     --owner-root /absolute/path/to/pinned-ai-worktree
   ```

   The Required CI Docker workflow checks out the pinned owner and runs this command
   as a mandatory job. Failure cannot become a skip or a successful gate.
4. The controller chooses a random project, creates owner-only temporary files and
   a two-day local CA/server certificate with `DNS:broker`, and builds the source
   API plus a separate AI delivery image. `uv==0.12.19` synchronizes the owner's
   existing delivery lock with `--locked --no-dev --no-editable`; the main AI lock
   and installed ML environment are never edited.
5. It starts only its own databases and broker. Broker Kafka and Admin listeners
   require TLS from startup. Bootstrap authentication/authorization is enabled in
   `.bootstrap.yaml`; auto topic creation is disabled. The temporary bootstrap
   administrator creates workload identities, three delete-only topic partitions
   and exact resource ACLs. Administrator credentials are confined to the broker
   and test control probe, not application mounts.
6. It creates separate database workload roles with `NOSUPERUSER NOCREATEDB
   NOCREATEROLE`, revokes public database connection and public schema creation,
   applies source migrations, and prepares the explicit mechanics outbox fixture.
   AI delivery has only SELECT/UPDATE on its outbox. Source consumer has bounded
   projection/checkpoint/quarantine table grants. Source API has only SELECT on
   forecast results/inbox. Its DB role cannot write results.
7. It starts source API and checkpoint consumer, executes the owner's actual AI
   delivery CLI and requires a receipt for exactly one event. It checks the exact
   original functional payload, event identity, broker partition/offset receipt,
   three durable partition cursors, one projection/inbox and authenticated HTTP
   history response. Original payload freshness is preserved; history may correctly
   become stale with wall-clock time. An unconfigured active head returns 503.
8. It checks broker denials for consumer writes, producer reads, foreign group/topic
   and topic creation; wrong password and untrusted CA require explicit client
   authentication/SSL errors. Anonymous Kafka metadata is unavailable and Admin
   requests return 401/403. Cross-database credentials are rejected, workload roles
   cannot create roles and the API reader cannot delete projections. Separate source
   and intelligence HTTP tokens cannot substitute for each other.
9. It kills only the owned consumer, resets the fixture outbox delivery receipt
   **as an explicit simulation of broker ACK before SQL receipt**, redelivers the
   unchanged event and restarts the consumer. It requires two transport receipts
   (`projected`, `duplicate`), contiguous durable offset 2 and exactly one projection
   and inbox. This is a controlled redelivery simulation, not a claim that this
   drill kills an AI process at the exact precommit instruction; that boundary has
   independent outbox/checkpoint tests in earlier increments.
10. On success/failure/interruption the controller removes its own project containers,
    volumes, networks and built images, checks label-scoped leftovers, and deletes
    temporary credentials and certificates. It never uses global prune or a shared
    project name. Inspect `ci-cd/reports/intelligence-runtime/report.json`, or the
    `intelligence-runtime-evidence` CI artifact: exact source/AI commits and lock hashes,
    stages, identities, payload digest, offsets, negative checks and cleanup result.
    Credentials, resolved Compose output, DB URLs and raw application logs are excluded;
    a failed bootstrap may include bounded, redacted broker startup diagnostics.

## Identity and resource grants

| Identity | Allowed resources | Main denial tested |
|---|---|---|
| `ai-producer` | WRITE/DESCRIBE exact v2 topic; cluster IDEMPOTENT_WRITE | Fetch topic |
| `source-consumer` | READ/DESCRIBE/DESCRIBE_CONFIGS exact v2 topic; READ/DESCRIBE exact checkpoint group; cluster DESCRIBE for topology | Produce, foreign group/topic, create topic, Admin API |
| `ai_worker` | AI database; SELECT/UPDATE outbox | Source database / create roles |
| `source_worker` | Source database; projection, inbox, transport, cursor and quarantine tables | AI database / create roles |
| `source_reader` | Source database; SELECT forecast projection/inbox | Write projection / create roles |
| Separate HTTP readers | Private, hashed, scoped policy files | Cross-use of source/intelligence credentials |

All workload ACL resource names are literal; the ACL host wildcard permits the
workload within this private, disposable project. Runtime containers see only their
own mounted credential directory. Docker/host administrators and the acceptance
probe remain trusted operators. HTTP inside this disposable private network is
plain HTTP; there are no public endpoints. A production runtime needs its own TLS
HTTP ingress, durable secret distribution/rotation, CA management, multi-replica
head revocation and service supervision. This fixture controller is not that deployment.

Reference configuration follows Redpanda's official
[25.3 bootstrap/authentication quickstart](https://docs.redpanda.com/streaming/25.3/get-started/quick-start/),
[authentication and SASL/TLS configuration](https://docs.redpanda.com/streaming/25.3/manage/security/authentication/),
[Admin TLS broker properties](https://docs.redpanda.com/streaming/25.3/reference/properties/broker-properties/)
and [Kafka ACL operation mapping](https://docs.redpanda.com/streaming/current/manage/security/authorization/acl/).
