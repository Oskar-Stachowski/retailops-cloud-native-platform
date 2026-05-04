# Sprint 7 Future Improvements — Users, Roles and Notifications

## Purpose

Sprint 7 introduces the first DevOps-facing access and operational-awareness layer for RetailOps.

The goal is not to build production authentication yet. The goal is to make the platform behave like a real internal operations tool by showing:

- who the current user is,
- what role and permissions the user has,
- which screens are protected by an access boundary,
- which notifications require attention,
- where future workflow write actions will connect.

This creates a bridge between the Sprint 5 dashboard, Sprint 6 Product 360 and later production-grade security, workflow and audit capabilities.

## Current Scope Boundary

Current implementation is intentionally local-first and mock-auth only.

Included now:

- `GET /users/demo`
- `GET /me`
- `GET /me/permissions`
- `GET /notifications`
- `POST /notifications/{notification_id}/read`
- frontend demo user switcher,
- notification indicator,
- basic role-aware Admin boundary,
- Profile page showing user, permissions and notifications,
- backend and frontend tests for the new contract.

Explicitly not included now:

- real login,
- OAuth/OIDC,
- JWT validation,
- sessions or cookies,
- password handling,
- database-backed users,
- persistent notification state,
- production-grade RBAC policy engine,
- audit log persistence,
- mutation of operational workflow actions.

## Recommended Future Implementation Order

### 1. Persist users, roles and notifications in PostgreSQL

Move demo users and notifications from Python constants to database tables.

Recommended future tables:

- `roles`
- `permissions`
- `users`
- `user_roles`
- `role_permissions`
- `notifications`
- `notification_reads`

Why first: it turns mock UI behavior into a real data contract without changing the user experience too much.

### 2. Add workflow write APIs

Add controlled mutation endpoints for operational work:

- approve recommendation,
- reject recommendation,
- assign alert,
- add comment,
- change alert status,
- create workflow action.

Why second: the current Product 360 and Dashboard already show decision signals. The next product value is allowing users to act on those signals.

### 3. Add audit trail and event history

Every workflow change should produce an immutable audit event.

Suggested fields:

- event id,
- actor user id,
- entity type,
- entity id,
- previous state,
- new state,
- timestamp,
- source service,
- correlation id.

Why third: once users can mutate state, auditability becomes a platform-quality requirement.

### 4. Replace mock identity with real authentication

Recommended options:

- AWS Cognito for AWS-native portfolio alignment,
- Auth0 for fast OIDC integration,
- Keycloak for self-hosted enterprise IAM learning,
- corporate SSO/OIDC in a real enterprise setting.

Why fourth: real auth should be added after the internal permission model and protected resource boundaries are clear.

### 5. Add policy-as-code authorization

Consider a policy layer such as Open Policy Agent or Cedar when authorization logic becomes more complex.

Example future questions:

- Can an Inventory Planner approve only inventory recommendations?
- Can a Commercial Analyst view revenue data but not operational assignment data?
- Can an Operations Manager close alerts across regions?

### 6. Add notification delivery channels

Future delivery channels:

- in-app notification center,
- email,
- Slack or Teams integration,
- webhook to incident-management tools.

Why later: delivery channels are useful only after notification semantics and ownership are stable.

## ADR-style Notes

### Option A — Real auth immediately

Pros:

- closer to production,
- stronger security story,
- useful for cloud deployment.

Cons:

- slows the sprint,
- adds configuration and secrets early,
- distracts from product workflow learning.

### Option B — Mock users and local role boundaries now

Pros:

- fast to implement,
- highly testable,
- no secrets,
- makes future auth boundary visible,
- good for portfolio storytelling.

Cons:

- not production security,
- role state is not persistent,
- users may confuse mock role checks with real RBAC.

Chosen for Sprint 7: Option B.

## Testing Improvements

Current minimum tests cover endpoint contracts and frontend service calls.

Future tests should add:

- forbidden route behavior in the browser,
- workflow mutation authorization tests,
- audit log creation tests,
- notification persistence tests,
- Playwright end-to-end test for user switching and notification read flow,
- OpenAPI contract snapshot tests.

## Observability Improvements

Future production implementation should emit:

- auth failure counters,
- permission denied counters,
- notification delivery metrics,
- workflow action latency,
- audit event creation failures,
- dashboard/user activity traces.

## Security Improvements

Future production implementation should add:

- JWT validation,
- issuer and audience checks,
- role claim mapping,
- short token lifetime,
- least-privilege service permissions,
- API rate limits,
- audit logs for sensitive reads and writes,
- secret management through cloud-native secret stores.

## Portfolio Talking Point

Sprint 7 is valuable because it shows that RetailOps is no longer only a read-only dashboard. It starts to behave like an internal enterprise operations platform with users, roles, notifications and access boundaries.
