# Sprint 5 — Dashboard and Operations View Future Improvements

## Purpose

Sprint 5 turns the RetailOps MVP from a technical API demo into a business-facing operational dashboard. The current implementation connects the frontend dashboard to real FastAPI endpoints for KPI summary, sales trend, alerts, recommendations, open work items, stock-risk summary, products, forecasts and inventory-risk signals.

The business purpose is to show how RetailOps supports decisions for Operations, Inventory Planning, Commercial and Management users:

- Which products need inventory attention?
- Are there open alerts or work items?
- Are there recommendations that require action?
- Is sales trend evidence available for management review?
- Can the platform prove that dashboard data is coming from backend APIs, not local mocks?

## Current Scope Boundary

The current scope is intentionally MVP-level:

- Dashboard data is read-only.
- The frontend consumes existing dashboard and core API endpoints.
- Sales trend is rendered as a table/list instead of a full charting library.
- Alerts, recommendations and work items are displayed as operational evidence, not as a complete workflow engine.
- Anomalies and Recommendations pages may remain scope-bound placeholders if dedicated entity-level APIs are not implemented yet.
- Authentication, authorization, user-specific views and audit trail are not part of this sprint.
- No new infrastructure, cloud services or Kubernetes resources are required.

This keeps Sprint 5 focused on business value and portfolio evidence without overengineering.

## Recommended Future Implementation Order

### 1. Stabilize dashboard API contracts

Add stronger typed response contracts for:

- `/dashboard/summary`
- `/dashboard/operational-visibility`
- `/dashboard/sales-trend`
- `/dashboard/alerts`
- `/dashboard/recommendations`
- `/dashboard/open-work-items`
- `/dashboard/stock-risk-summary`

Recommended next step: add API contract tests that validate field names, response shapes and empty-state behavior.

### 2. Add proper charting for sales trend

Replace the Sprint 5 table-style sales trend with a chart component.

Recommended implementation options:

- lightweight SVG chart without dependencies,
- Recharts if the project accepts a charting dependency,
- backend-generated trend buckets with fixed time granularity.

Decision point: avoid adding a charting dependency until the dashboard contract is stable.

### 3. Build Operations Center

Move alert, recommendation and work-item handling into a dedicated Operations Center page.

Future features:

- Today’s Issues,
- Critical Actions,
- owner/role assignment,
- status changes,
- action history,
- CSV export for operational review.

This naturally leads into Sprint 6 Product 360 and Operational Workflow.

### 4. Add workflow actions and audit trail

Add backend support for state transitions:

- recommendation accepted/rejected/escalated,
- alert acknowledged/resolved,
- work item opened/in progress/done,
- audit event written for every state change.

Recommended backend scope:

- `workflow_actions` table,
- repository + service layer,
- POST/PATCH endpoints,
- integration tests for state changes.

### 5. Add role-aware executive and operational views

Introduce role-specific dashboard variants:

- Executive: high-level business outcomes and risk exposure,
- Operations Manager: alerts, work items and SLA signals,
- Inventory Planner: stockout/overstock risk and forecast context,
- Commercial Analyst: sales trend and demand signals,
- DevOps: health, readiness and service status.

### 6. Add observability and SLO evidence

Once the dashboard is stable, connect it with platform observability:

- API latency,
- error rate,
- data refresh age,
- dashboard availability,
- open alert backlog,
- failed backend dependency count.

This should later feed Prometheus/Grafana and the project evidence matrix.

## Suggested Future API Enhancements

- Add pagination/filtering to dashboard-level collections.
- Add severity and status filters for alerts.
- Add owner and due-date filters for work items.
- Add sales trend bucket parameters, for example `?period=daily|weekly|monthly`.
- Add forecast-vs-actual endpoint once actual demand data is stable.
- Add anomaly drill-down endpoint when anomaly detection is implemented.

## Suggested Future UI Enhancements

- Convert sales trend table into a chart.
- Add clickable drill-down from KPI cards to filtered lists.
- Add dashboard timestamp and stale-data warning.
- Add empty-state explanations per panel.
- Add screenshot-ready executive mode for portfolio/demo use.
- Add CSV export for dashboard evidence.

## Testing Improvements

Recommended future tests:

- frontend service tests for every dashboard endpoint,
- dashboard render tests with mocked API payloads,
- API contract tests for response shapes,
- empty-state tests for no alerts/recommendations/work items,
- backend repository/service tests for computed indicators,
- future E2E smoke test for dashboard loading through Docker Compose.

## Conscious Non-Goals

The following are intentionally not included in Sprint 5:

- full workflow engine,
- user login and RBAC,
- audit log writes,
- real-time websocket updates,
- ML-based anomaly detection,
- charting dependency,
- cloud deployment,
- Kubernetes manifests,
- production-grade observability stack.

These belong to later platform maturity stages.

## Portfolio Evidence To Capture

Capture these after implementation:

- screenshot of the dashboard with KPI cards,
- screenshot of source-status cards showing connected backend endpoints,
- screenshot of sales trend / alerts / recommendations / work items sections,
- screenshot of Swagger showing dashboard endpoints,
- terminal output for frontend tests, lint and build,
- terminal output for backend tests,
- GitHub Actions green run.
