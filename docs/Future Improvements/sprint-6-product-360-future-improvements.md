# Product 360 Future Improvements

## Purpose

Product 360 gives operators, inventory planners and analysts one product-level view that connects catalog data with sales, inventory, forecasts, anomalies, alerts, recommendations and workflow history.

The Sprint 6 implementation is intentionally read-only. It proves that the platform can aggregate operational signals around a single product without introducing workflow mutations too early.

## Current Scope Boundary

Sprint 6 Product 360 includes:

- `GET /products/{product_id}/360` as a composite read API.
- Product identity and catalog metadata.
- Product-level operational metrics.
- Latest stock-risk status.
- Related sales, inventory snapshots, forecasts, anomalies, alerts, recommendations and workflow actions.
- Frontend drill-down route from the Products table.
- Minimal backend and frontend tests.

Sprint 6 deliberately does not include:

- Approve/reject recommendation actions.
- Alert assignment or reassignment.
- Workflow comments from the UI.
- Authentication or role-based permissions.
- Optimistic UI updates.
- Charts or advanced visual analytics.
- ML model explanations beyond existing forecast and recommendation records.

## Recommended Future Implementation Order

1. **Improve read model quality**
   - Join product SKU/name into anomaly, alert and recommendation rows.
   - Add clearer business labels for anomaly and recommendation types.
   - Add backend response examples to OpenAPI docs.

2. **Add workflow write APIs**
   - `POST /alerts/{alert_id}/actions`
   - `POST /recommendations/{recommendation_id}/approve`
   - `POST /recommendations/{recommendation_id}/reject`
   - Record every state change in `workflow_actions`.

3. **Add authorization boundaries**
   - Operators can acknowledge alerts.
   - Inventory planners can approve replenishment actions.
   - Analysts can comment but not approve operational changes.
   - Admins can override workflow state.

4. **Add auditability and observability**
   - Structured logs for workflow mutations.
   - Metrics for open work items, action latency and approval rate.
   - Trace IDs between frontend calls and API logs.

5. **Add richer UI**
   - Timeline layout for actions and alerts.
   - Trend charts for sales, stock and forecast confidence.
   - Filters by severity, status and date.
   - Empty-state explanations for products without anomalies or recommendations.

6. **Add production hardening**
   - Pagination for every related section.
   - Contract tests for Product 360 schema stability.
   - Load/performance checks for composite read endpoints.
   - Query indexes if Product 360 latency grows.

## Decision Notes

### Why a composite endpoint?

A Product 360 page needs many related datasets at once. Calling eight separate endpoints from the frontend would work, but it would make the UI responsible for orchestration, partial failures and response consistency.

The composite endpoint keeps orchestration in the backend service layer. This is easier to test, document and evolve.

### Why read-only first?

Workflow mutations are higher-risk than read models. They require stronger validation, authorization, audit history and error handling. Product 360 should first prove that the platform can show trustworthy operational context before allowing users to change business state.

## Future Definition of Done

A future production-ready Product 360 should have:

- Role-based access control.
- Full workflow mutation APIs.
- Audit trail for every business action.
- Frontend timeline view.
- Pagination and filtering for related rows.
- Contract tests for the API response shape.
- Observability for endpoint latency, error rate and workflow action volume.
- Clear documentation of user permissions and workflow state transitions.
