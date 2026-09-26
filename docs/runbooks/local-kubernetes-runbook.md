# Local Kubernetes runtime and rollback

Use `make k8s-runtime-drill` to build two committed application versions, start
an isolated kind cluster, exercise RetailOps, and remove the test resources.
This is the local foundation before RetailOps AI; EKS, Helm and production
storage remain separate work.

## Prerequisites

- Docker running with at least 4 GiB memory available to its VM.
- kind **v0.31.0**, kubectl **v1.35.x or v1.36.x**, Ruby, Python 3.11+, Node 22.
- Git history containing the predecessor `cb0c79848247612bf71fb9ccf63a8ff3847b5ca1`.
- `npm ci --prefix frontend` and `cd frontend && npx playwright install chromium`.
- For static checks: Kubeconform, Conftest and Checkov (`make k8s-ci`).

On macOS, an installed Google Chrome can be used instead of downloading Chromium:

```bash
PLAYWRIGHT_BROWSER_CHANNEL=chrome make k8s-runtime-drill
```

On Linux/CI:

```bash
make k8s-ci
make k8s-runtime-drill
```

The blocking Kubernetes CI workflow runs both the existing manifest/policy gates
and this actual kind runtime drill. The runtime uses the host's native Linux
architecture: ARM64 on Apple Silicon, AMD64 on GitHub's Ubuntu runner. Images
are built once from Git archives, loaded into kind with `imagePullPolicy: Never`,
and checked against the container runtime's image IDs and source labels.
These source builds **are not the signed GHCR artifacts of v0.2.1**, which were
published for AMD64 only. A native ARM64 registry release is still separate work.

## What the drill does

1. Generates a unique `retailops-k8s-*` cluster name, temporary kubeconfig and
   random database credentials. It never selects the user's current context,
   reads their local runtime secret file, changes `/etc/hosts`, or reuses a cluster.
2. Installs the digest-pinned Kubernetes 1.35.0 node image, kindnet v1.0.1 with
   NetworkPolicy enforcement, and Traefik v3.7.13. The infrastructure manifests
   are in `scripts/kubernetes/`; RetailOps workload policies stay in `k8s/`.
3. Creates the namespace, Services, ConfigMaps, Secret and PVCs; starts PostgreSQL
   and Redpanda; waits for migrations, demo seed and all six topic initializations;
   then starts API, frontend and the realtime consumer.
4. Verifies NetworkPolicy denial for an unlabelled Pod and a foreign namespace,
   with an allowed same-Pod control using a direct Service IP. DNS and internal
   communication are also exercised by the application and streaming path.
5. Publishes a sales event twice through Kafka, checks one processed database
   event and three metric rows, and verifies its presence in the live API.
   This exercises the existing metrics consumer, not a new business event handler.
6. Writes three business decisions through the deployed frontend/API and replays
   five idempotent actions. It checks the dashboard and Product 360 in a real
   browser, including page reloads.
7. Stops PostgreSQL. `/health` must stay 200 and `/ready` become 503 on the API
   Pod; the API Service must lose all ready endpoints and ingress must fail.
   Restarts PostgreSQL on the same PVC and compares the stored data and schema.
8. Restarts Redpanda, API, frontend and consumer; confirms the broker retained the
   published event and topics, and the database retained business history.
9. Updates all application workloads (including consumer/init images), verifies
   them, and adds a new comment. Stops API to detect HTTP 502 through ingress,
   then deploys the recorded previous images and verifies rollback plus another
   new write. No rebuild, restore, downgrade or reseed happens during rollback.
10. Captures reports, removes only the generated cluster and its local test image
    tags, and records cleanup success/failure. Deleting kind destroys its PVC data.

The predecessor defaults to the reviewed step-2 commit; the candidate defaults
to committed `HEAD`. The script records whether the working tree was dirty.
To select specific compatible commits:

```bash
python3 scripts/kubernetes/drill.py \
  --previous-ref cb0c79848247612bf71fb9ccf63a8ff3847b5ca1 \
  --candidate-ref HEAD
```

Both commits must be distinct, ordered by ancestry, and have exactly the same
migration history. The live database head must match that contract before
update/rollback. For schema-changing releases, use a reviewed recovery or
forward-fix plan; see [database restore](db-restore.md).

## Routing and persistence

```text
127.0.0.1:random-port -> kubectl port-forward -> Traefik
  -> Ingress -> retailops-frontend:80 -> Nginx :8080
    /            -> React SPA
    /api/*       -> api:8000 -> RetailOps API -> postgres:5432
Realtime consumer -> redpanda:9092 and postgres:5432
```

The base Ingress uses `retailops.local`. The isolated drill adds a hostless rule
for its loopback-only browser connection; it also requests the named host.
`api` and `retailops-api` are ClusterIP Services selecting the same API Pods.
The alias matches the existing release image's Nginx upstream and also makes
frontend port-forwarding work. API path stripping stays in that tested Nginx
configuration; no controller-specific rewrite annotation is required.

Ingress NGINX was retired in March 2026; this path uses Traefik instead.
See the [Kubernetes announcement](https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/)
and [Traefik provider documentation](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/).

The dev overlay uses separate 1 GiB `ReadWriteOnce` PVCs and `Recreate` deployments
for PostgreSQL and Redpanda. PostgreSQL runs as the Alpine image's UID/GID 70;
`fsGroup` and a `PGDATA` subdirectory permit initial setup without root capabilities.
A cluster needs a default StorageClass (kind supplies `standard`). The volumes
survive Pod replacement, **not deletion of the local cluster or host disk loss**.
This is single-node development storage, not HA or a substitute for backups.

## Reports and troubleshooting

Each run writes `ci-cd/reports/k8s-runtime/retailops-k8s-*/report.json`, command
logs, workload logs, resource/events snapshots, and browser traces on failure.
CI uploads these as `kubernetes-runtime-evidence`. Do not commit raw generated
secrets, kubeconfigs or full environment logs; curate evidence under
`docs/evidence/kubernetes/`.

The report compares row fingerprints, schema and sequences for every table
except `realtime_consumer_state`, whose start/stop counters and timestamps change
by design. Event history, metric observations and workflow audit rows remain
in the comparison. Timings describe a tiny demo fixture, not production RTO/RPO.

A failure returns a nonzero exit code. Start with the last command in
`commands.log`, then `events.txt` and the relevant workload log. Common causes:

- Insufficient Docker memory: check VM allocation before rerunning.
- Image download errors: restore registry connectivity; do not replace pins with `latest`.
- Pending PVCs: inspect the cluster's default StorageClass/provisioner.
- Failed jobs: inspect migration/seed/topic-init status and dependency readiness.
- Blocked traffic: retain application labels, Traefik namespace and CoreDNS rules;
  do not bypass NetworkPolicy to make the test pass.

The script cleans up on ordinary failures. If the process is forcibly killed,
use the **exact generated name and kubeconfig path from its command log**:

```bash
kind delete cluster --name retailops-k8s-EXACT_RUN_ID --kubeconfig /EXACT/TEMP/PATH/kubeconfig
```

Do not delete another cluster or run a global Docker prune. Unrelated Docker
containers and Kubernetes contexts are outside this drill.
