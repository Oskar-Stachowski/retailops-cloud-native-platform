# Daily AI forecasts in the existing RetailOps UI

AI10 remains in progress. The existing `/forecasts` page now includes a separate
daily AI read panel. Its data comes from the existing authenticated
`/intelligence/v2/forecasts` projection. The earlier product-period planning view
retains its meaning. Anomaly and model stockout views require their owners'
qualified final contracts and are not provided by this increment.

## Configure and use

1. Deploy the reviewed projection, checkpoint consumer and forecast publication
   selection increments first. Follow [approved head selection](intelligence-approved-head.md).
   No new database migration, model training or promotion is introduced here.
2. Expose the existing frontend and its `/api/` reverse proxy on the same HTTPS
   origin. The AI panel always uses that relative path and refuses a remote
   plain HTTP origin. Loopback HTTP is allowed for isolated development/CI.
   Its credentials never follow `VITE_API_BASE_URL` or an HTTP redirect.
3. Using your secret manager, issue a dedicated personal read-only opaque
   credential for each authorized reviewer. Put only its SHA-256 digest and
   explicit product/location/channel/release grants in the private server-side
   `RETAILOPS_INTELLIGENCE_ACCESS_POLICY` file described in
   [projection access](intelligence-v2.md). Do not give a browser service,
   pipeline, admin or source-bundle credentials. Demo users do not authorize AI.
   Keep the file owned by the API user, mode 0600, with one hard link and no
   symlink. The server rereads it on every request; an invalid replacement fails
   closed. Replace it atomically to avoid an intermediate partial file.
4. Open **Forecasts**, enter the personal credential in **AI forecasts** and
   select **Connect AI forecasts**. The default view is the operator-selected
   complete publication. An absent, invalid or expired selection is displayed
   as unavailable. The application never substitutes legacy or fixture results.
5. Inspect product, selling location, channel, UTC origin, target date/horizon,
   candidate mean, reference median and the server-evaluated freshness reason.
   These are daily observed sales units. The model's preserved reference interval
   is available under **View lineage**; the panel does not infer a confidence
   percentage or a stockout probability from it. Excluded numerical values stay
   unavailable, with the producer's exclusion reason in lineage.
6. Open **View lineage** to fetch that exact immutable result again through the
   authenticated API. Review its model/version, release/run, source/curated/
   feature/output IDs, computation receipt, approval/runtime/image checksums,
   watermark and timestamps. IDs are displayed as data, not used as arbitrary
   external URLs. An operational action remains a human workflow.
7. Use **Next AI page** for bounded pages of 50 rows. Each following page binds
   the first page's view digest. If the operator selection changes, refresh from
   the first page; no automatic merging of different publications occurs.
   **Immutable history** is explicitly historical and does not imply current
   approval. The older replay cannot choose the active publication.
8. Disconnect when finished. Credentials and displayed results are cleared on
   disconnect, hiding the tab, page exit, a demo-user switch or the five-minute
   memory window. They are not put in URLs, browser storage, build variables or
   logs. A late in-flight response cannot restore cleared results. The active
   selection's expiry independently clears its displayed rows. Revocation takes
   effect on the next server request; it does not remotely erase an already
   displayed browser screen. Scoped success and error responses use `no-store`
   and vary on Authorization.

## Acceptance

`scripts/intelligence-ui/drill.py` is a mandatory frontend Required CI job. It
runs migrations in its own disposable PostgreSQL 16 service, projects complete
schema-valid invented publications, starts the current API on an owned socket,
builds the actual frontend, and uses Chromium through Vite's same-origin proxy.
It proves 70 active results on 50/20 pages, exact API payloads, rendered values
and lineage, foreign-scope denial, anonymous/demo impersonation denial, head
replacement conflict, explicit historical staleness, credential-storage absence,
disconnect cancellation and live policy revocation. The screenshot is taken
after the password input is removed. Traces/videos and automatic screenshots
are disabled for this credential-bearing test; only the selected sanitized
fixture screenshot/report and server startup logs are uploaded.

Run only against a database you created specifically for the drill, with
`DATABASE_URL` and `RETAILOPS_UI_DISPOSABLE_DB=1`, after installing the locked
frontend dependencies and Chromium plus API dev requirements:

```sh
PYTHONPATH=.:services/api python scripts/intelligence-ui/drill.py
```

It fails if the owned ports 8000/4173 are occupied and stops only its own server
processes. Private temporary credentials and control files are removed on both
success and failure. CI owns disposal of its database; the script does not
reset a shared database. Receipt and screenshot are in
`ci-cd/reports/intelligence-ui/`. This is HTTP fixture acceptance, not a model
quality, production HTTPS, browser identity-provider or deployed Nginx proof.
The unchanged Compose/Kubernetes gates separately check the existing deployed
frontend stack. Complete three-model temporal E2E and snapshot/replay remain
outstanding for AI10.

Rollback consists of returning the frontend/API image pair to the reviewed
previous release. There is no schema downgrade in this increment. Preserve the
private grant policy; removing a personal credential revokes future reads
without an API restart.
