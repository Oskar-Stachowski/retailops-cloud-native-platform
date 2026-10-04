# Personal AI suggestion review in RetailOps

The existing **Recommendations** page includes **AI suggestions**, backed by
the read-only `/intelligence/v2/recommendations` projection. This increment
completes a fixture integration; AI10 remains in progress. Real assistant outbox
publication, model qualification, snapshot/replay and the three-model 102-day
acceptance are separate requirements. No model training or new migration is
introduced by this UI increment.

## Configure and review

1. Review the [suggestion projection](intelligence-suggestion-projection.md)
   and its schema expansion before using this frontend/API image pair. Keep the
   fixture transport gate disabled in normal operation. The UI never seeds data
   or enables that gate; its current results come only from the API projection.
2. Serve the frontend and `/api/` proxy on the same HTTPS origin. Remote HTTP
   access is refused; isolated loopback development may use HTTP. Personal
   credentials cannot follow `VITE_API_BASE_URL`, cookies or redirects.
3. Issue a personal `suggestion:read` credential through your secret manager.
   Put its SHA-256 digest and explicit product/location/channel, policy/config
   and all model-reference grants in the private API-owned mode-0600
   `RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY` file. Use the exact policy
   shape in the projection runbook and replace it atomically. Demo identity,
   forecast credentials and source-bundle/service credentials do not grant this
   capability. Grant review access only to the intended products and locations.
4. Open **Recommendations**, enter the personal credential and choose
   **Connect AI suggestions**. **Current suggestions** shows only publications
   that the database considered current at read time. Empty or unavailable
   results are explicit; the panel does not populate itself from legacy signals.
5. Inspect the proposed action, review type, priority and UTC expiry. Open
   **View suggestion evidence** to re-read that exact immutable ID. Review the
   rationale, summary, evidence/model references, trace/answer/candidate IDs,
   policy checksum, agent configuration and source/creation/receipt timestamps.
   References are escaped text, not executable HTML or automatically opened
   URLs. Human review is required; execution remains unauthorized. The panel
   provides no accept, approve, order, reject or execute action.
6. Use **Next suggestion page** for 50-row pages. The next page binds the same
   digest; a new publication, expiry or scope change can invalidate it. Refresh
   from the first page after a conflict. Results from different views are not
   appended together. The API limits each view to 500 scoped results.
7. Choose **Immutable history** to inspect past or future publications. Original
   `freshness_status=current` is publication data; the separate **Freshness at
   read** can be stale or unknown. Historical visibility does not renew validity.
   Freshness derives from the database clock. The browser subtracts the full
   request duration from the remaining lifetime and uses a monotonic timer, so
   a skewed workstation clock cannot extend it. When any displayed current row
   expires, its page and detail are cleared and must be refreshed. Already
   expired history stays explicitly stale; future history stays unknown until
   a fresh server read. No quantity, risk probability or quality approval is
   inferred from a suggestion's priority or freshness.
8. Disconnect after review. The credential and results exist only in memory
   for at most five minutes. Disconnect, a hidden tab, page exit, demo-user
   change or unmount clears access. Abort and generation checks prevent late
   replies from restoring cleared results. Revocation is checked by the running
   API on every request, without a restart; it cannot erase an already displayed
   screen remotely. A denied refresh clears displayed data and the credential.
   All scoped API success/error responses use `no-store`.

## Required acceptance and rollback

`scripts/intelligence-ui/drill.py` owns a disposable PostgreSQL service in CI,
migrates it, projects schema-valid invented forecast and suggestion fixtures,
starts the current API and built frontend on owned sockets, and executes both
credential-bearing Playwright tests with Chromium. It refuses an ordinary DB
unless its caller sets `RETAILOPS_UI_DISPOSABLE_DB=1`; use only a DB created for
this drill. Local Docker is not required or started by this change.

Suggestion acceptance covers 70 current results on 50/20 pages; 72 scoped
history results with expired/future payloads; two foreign product/model results
excluded before counts; exact immutable payload and rendered evidence; escaped
HTML-shaped references; 401 anonymous/forecast credential, 403 foreign scope,
422 demo override and 409 changed view; no execution controls or stored secrets;
demo/hidden-event clearing, completed in-flight disconnect cancellation and live
policy revocation. A fixture projected during the test expires after eight
seconds: despite an eight-year workstation clock skew the browser clears both
page and evidence, while actual API history preserves its payload with stale
freshness. The hidden-state handler is exercised with a synthetic visibility
event; this does not qualify every browser's real background lifecycle.

The owned short-expiry fixture writer is enabled only by the disposable-drill
guard; it is not a product endpoint. Secrets/control files stay in a private
temporary directory and are removed on all exits. Servers are stopped only if
created by this drill. Traces/videos and automatic screenshots are disabled;
chosen fixture screenshots are taken after the password input is removed.
Evidence is in `ci-cd/reports/intelligence-ui/report.json` and the two screenshots.
HTTP fixture acceptance does not qualify production HTTPS/IdP/Nginx or an actual
assistant emitter. Existing Compose/kind gates separately check image rollback.

Rollback restores the previously reviewed frontend/API images while retaining
the expanded database and private grant policies. This increment performs no
schema downgrade or database reseeding during rollback.
