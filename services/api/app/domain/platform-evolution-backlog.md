# RetailOps Domain Model — Future Improvements

> This document collects advanced improvements that are intentionally **out of scope for the current Sprint 3 domain-model task**.  
> The current goal is to keep the MVP model understandable, testable and aligned with the first RetailOps flow:  
> `Product + Sale + InventorySnapshot -> Forecast / Anomaly -> Alert -> Recommendation -> WorkflowAction -> User decision`.

---

## 1. Purpose

The purpose of this document is to keep a backlog of possible advanced improvements without overloading the current MVP implementation.

These ideas may become useful when RetailOps moves from a documentation/API-first MVP toward a more production-like platform with persistence, security, workflows, observability, data quality, MLOps and enterprise operations.

---

## 2. Current Scope Boundary

### Current MVP Domain Models

The current Sprint 3 implementation should focus on:

- `Product`
- `Sale`
- `InventorySnapshot`
- `User`
- `Alert`
- `WorkflowAction`
- `Anomaly`
- `Forecast`
- `Recommendation`

### Future Domain Extensions

The following entities should **not** be added to the current Pydantic implementation unless a later task explicitly requires them:

- `Order`
- `Supplier`
- `Promotion`
- `PriceSnapshot` / `PriceHistory`
- `Channel` as a full entity
- `Warehouse` as a full entity
- `Category` as a full entity
- `DataQualityCheck`
- `ModelVersion`
- `ForecastRun`
- `IngestionBatch`
- `DataSource`
- `AuditLog`

---

## 3. Recommended Future Implementation Order

### Priority 1 — Good next improvements after MVP models are stable

These are valuable but should be done after the current model is committed:

1. Add dedicated API schemas: `Create`, `Read`, `Update`.
2. Add stricter workflow status transition validation.
3. Add tests for all validators and enum constraints.
4. Add OpenAPI examples for key domain models.
5. Add sample seed data for MVP scenarios.
6. Add ADR for Pydantic domain models vs SQLAlchemy persistence models.

### Priority 2 — When adding persistence

1. Introduce SQLAlchemy ORM models separately from Pydantic API/domain schemas.
2. Add Alembic database migrations.
3. Add database-level constraints and indexes.
4. Add foreign key relationships.
5. Add integration tests using a local PostgreSQL container.

### Priority 3 — When moving toward production-like platform maturity

1. Add proper authentication and authorization.
2. Add RBAC / ABAC model.
3. Add audit trail and correlation IDs.
4. Add event-driven domain events.
5. Add data quality and MLOps governance entities.
6. Add observability fields and metrics.
7. Add retention, replay and backfill strategy.

---

## 4. Domain Model Refinements

### 4.1 Base Model Improvements

Possible improvements:

- Keep using a shared `RetailOpsBaseModel`.
- Add `extra="forbid"` to prevent unknown fields.
- Add `str_strip_whitespace=True` to normalize strings.
- Consider adding common timestamp behavior through a shared base class.
- Consider a separate `TimestampedModel` for entities that need both `created_at` and `updated_at`.

Possible future structure:

```text
RetailOpsBaseModel
  -> TimestampedModel
      -> Product
      -> User
      -> Alert
```

Decision note:

- Do this only when timestamp duplication becomes annoying.
- Avoid abstracting too early while the model is still changing.

---

### 4.2 UTC Time Standardization

Future improvement:

- Normalize all datetimes to UTC-aware values.
- Reject or normalize timezone-naive datetimes.
- Document the API contract: all datetime values are stored and returned in UTC.

Why it matters:

- Prevents bugs when comparing `datetime.now(timezone.utc)` with timezone-naive values.
- Makes logs, metrics, traces and business events easier to correlate.

Potential rule:

```text
All persisted and API-exposed datetimes must be UTC-aware ISO 8601 timestamps.
```

---

### 4.3 Stronger Date and Period Validation

Possible future validators:

- `created_at <= updated_at`
- `sold_at <= created_at`
- `recorded_at <= ingested_at <= created_at`
- `forecast_period_start <= forecast_period_end`
- `period_start <= period_end <= detected_at`
- `generated_at <= expires_at`

Important design rule:

Business problems such as stale inventory data should usually not be rejected at validation level. They should be accepted and converted into alerts or anomalies.

Example:

```text
Validation error:
  recorded_at > ingested_at

Business anomaly:
  inventory snapshot is 36 hours old
```

---

### 4.4 Money Handling

Current MVP approach:

- `unit_price`
- `total_amount`
- `currency`

Possible future improvements:

- Use `Decimal` consistently for money.
- Quantize currency amounts to two decimal places where appropriate.
- Add validation for `total_amount == quantity * unit_price` when discounts are not in scope.
- Later relax the rule when `Promotion`, `Discount`, `Tax` or `PriceAdjustment` entities are introduced.
- Consider a value object such as `Money(amount, currency)`.

Decision point:

```text
Option A: strict MVP total amount validation
Option B: flexible total amount to support future promotions and discounts
```

Recommended future decision:

- Start strict if seed data is simple.
- Move to flexible once promotions, taxes or discounts are modeled.

---

### 4.5 Machine-Friendly Enum Values

Future improvement:

Use lower snake case enum values for API stability.

Prefer:

```text
inventory_planner
category_manager
analyst
admin
```

Over:

```text
Inventory Planner
Category Manager
Analyst
Admin
```

Why:

- Better for APIs.
- Better for tests.
- Easier to filter and serialize.
- UI can still display human-readable labels separately.

---

### 4.6 More Precise Foreign Key Field Names

Future improvement:

Use names that explain the relationship, not only the target entity.

Examples:

```text
Alert.user_id -> Alert.assigned_to_user_id
WorkflowAction.user_id -> WorkflowAction.performed_by_user_id
Recommendation.user_id -> Recommendation.approved_by_user_id, if ever needed
```

Why:

- `user_id` is ambiguous.
- Precise names improve API readability and reduce mistakes in tests and database queries.

---

## 5. Workflow and Alerting Improvements

### 5.1 Alert State Machine

Future improvement:

Define valid status transitions for `Alert`.

Example lifecycle:

```text
open -> acknowledged -> in_progress -> resolved
open -> dismissed
acknowledged -> dismissed
in_progress -> dismissed
resolved -> open
```

Invalid examples:

```text
resolved -> in_progress
open -> resolved, if acknowledgement is required
```

Why:

- Prevents impossible workflow states.
- Makes audit trail more meaningful.
- Produces strong unit-test scenarios.

---

### 5.2 Action-Type-Specific Validation

Future improvement:

Add validation rules based on `WorkflowAction.action_type`.

Examples:

- `dismiss` requires a comment.
- `escalate` requires target team or target user.
- `assign` requires assigned user.
- `resolve` may require a resolution note.
- `reopen` may require a reason.

Why:

- Improves governance.
- Makes decision history more useful.
- Helps distinguish real business decisions from accidental clicks.

---

### 5.3 SLA and Escalation Model

Possible future fields:

- `due_at`
- `acknowledged_at`
- `resolved_at`
- `escalated_at`
- `sla_breached`
- `escalation_level`
- `assigned_team`

Possible future scenarios:

- Critical alert not acknowledged within 30 minutes.
- Stockout risk not resolved before forecasted peak demand.
- Stale inventory alert escalated to platform team.

---

### 5.4 Notification Model

Future entity:

```text
Notification
```

Possible fields:

- `id`
- `alert_id`
- `recipient_user_id`
- `channel`
- `status`
- `sent_at`
- `failed_reason`

Possible channels:

- email
- Slack / Teams
- dashboard
- webhook

---

## 6. API Schema Improvements

### 6.1 Separate Create, Read and Update Schemas

Future improvement:

Split models by API purpose.

Example:

```text
ProductCreate
ProductRead
ProductUpdate
Product
```

Why:

- API clients should not provide server-generated fields such as `id`, `created_at`, `updated_at`.
- Partial updates need optional fields.
- Read models may include computed fields.

Example distinction:

```text
ProductCreate: sku, name, category, brand
ProductRead: id, sku, name, status, created_at, updated_at
ProductUpdate: name?, category?, brand?, status?
```

---

### 6.2 OpenAPI Examples

Future improvement:

Add example payloads for:

- creating a product
- submitting a sale record
- submitting inventory snapshot
- reading active alerts
- acknowledging an alert
- resolving an alert
- accepting / rejecting a recommendation

Why:

- Improves developer experience.
- Makes the project easier to understand for recruiters.
- Helps with contract testing later.

---

### 6.3 API Versioning

Future improvement:

Introduce route versioning when contracts become stable.

Example:

```text
/api/v1/products
/api/v1/sales
/api/v1/alerts
```

Why:

- Prevents breaking clients when models evolve.
- Creates a more production-like API design.

---

### 6.4 Filtering, Sorting and Pagination

Future improvement:

Add standard query patterns:

```text
GET /alerts?status=open&severity=critical
GET /products?category=electronics
GET /sales?product_id=...&from=...&to=...
GET /forecasts?product_id=...&period_start=...
```

Why:

- Dashboards need filtered views.
- Large datasets cannot be returned in one response.
- Pagination becomes necessary for production-like data volumes.

---

## 7. Persistence and Database Improvements

### 7.1 SQLAlchemy Models

Future improvement:

Introduce SQLAlchemy models separately from Pydantic models.

Recommended separation:

```text
Pydantic model = API/domain contract
SQLAlchemy model = database persistence mapping
```

Why:

- Avoid mixing API validation with database behavior.
- Makes future migrations and persistence logic cleaner.

---

### 7.2 Alembic Migrations

Future improvement:

Use Alembic for database schema changes.

Why:

- Tracks schema history.
- Makes CI/CD database changes reviewable.
- Enables local, staging and production environment consistency.

---

### 7.3 Database Constraints

Future database-level constraints:

- unique `Product.sku`
- non-negative `Sale.quantity`
- non-negative inventory quantities
- valid foreign keys to `Product`, `User`, `Alert`, etc.
- valid time order constraints where supported

Why:

- Pydantic validates application input.
- Database constraints protect the system even when data comes from another path.

---

### 7.4 Index Strategy

Potential indexes:

- `Product.sku`
- `Sale.product_id, sold_at`
- `InventorySnapshot.product_id, recorded_at`
- `Alert.status, severity`
- `Alert.product_id`
- `WorkflowAction.alert_id, created_at`
- `Forecast.product_id, forecast_period_start, forecast_period_end`

Why:

- Dashboard queries will often filter by product, time period, status and severity.

---

### 7.5 Soft Delete and Archival

Future improvement:

Consider soft deletion for selected entities.

Possible fields:

- `deleted_at`
- `archived_at`
- `is_active`

Use cases:

- retired products
- archived alerts
- old recommendations
- historical forecasts

Warning:

- Soft delete increases query complexity.
- Do not add it before it is really needed.

---

## 8. Future Domain Entities

### 8.1 Order

Future purpose:

Represent an order received or created in the retail process.

Possible fields:

- `id`
- `product_id`
- `quantity`
- `order_status`
- `ordered_at`
- `expected_delivery_at`
- `received_at`
- `source_system`

Potential scenarios:

- delayed order
- incomplete fulfillment
- order volume spike
- replenishment status tracking

---

### 8.2 Supplier

Future purpose:

Represent a supplier that can provide products.

Possible fields:

- `id`
- `name`
- `supplier_code`
- `status`
- `lead_time_days`
- `reliability_score`

Potential relationship:

```text
Product N:N Supplier
```

Potential scenarios:

- supplier delay risk
- replenishment lead time analysis
- preferred supplier recommendation

---

### 8.3 Promotion

Future purpose:

Represent sales campaigns and promotions affecting demand.

Possible fields:

- `id`
- `product_id`
- `promotion_type`
- `discount_percentage`
- `start_date`
- `end_date`
- `channel`

Potential scenarios:

- sales spike due to promotion
- promotion ended, sales drop is not a true anomaly
- false positive anomaly explanation

---

### 8.4 PriceSnapshot / PriceHistory

Future purpose:

Track prices over time.

Possible fields:

- `id`
- `product_id`
- `price`
- `currency`
- `valid_from`
- `valid_to`
- `channel`

Potential scenarios:

- pricing anomaly
- margin risk
- promotion impact
- price change vs sales trend analysis

---

### 8.5 Channel as Full Entity

Current MVP:

- `Channel` can remain an enum.

Future purpose:

Model sales channels as entities when they have their own attributes.

Possible fields:

- `id`
- `name`
- `channel_type`
- `region`
- `status`
- `owner_team`
- `fee_percentage`

Potential scenarios:

- marketplace sales anomaly
- channel-specific forecast
- online vs store performance

---

### 8.6 Warehouse as Full Entity

Current MVP:

- `warehouse_code` is enough.

Future purpose:

Model warehouses as entities when logistics scope expands.

Possible fields:

- `id`
- `warehouse_code`
- `name`
- `region`
- `status`
- `capacity`

Potential scenarios:

- regional stockout risk
- warehouse data freshness
- stock transfer recommendation

---

### 8.7 Category as Full Entity

Current MVP:

- `Product.category` can remain a string.

Future purpose:

Model category ownership, hierarchy and reporting.

Possible fields:

- `id`
- `name`
- `parent_category_id`
- `owner_user_id`

Potential scenarios:

- category manager dashboard
- category-level sales drop
- category-level forecast accuracy

---

## 9. Data Quality Improvements

### 9.1 DataQualityCheck Entity

Future entity:

```text
DataQualityCheck
```

Possible fields:

- `id`
- `dataset_name`
- `check_type`
- `status`
- `failed_records_count`
- `total_records_count`
- `severity`
- `checked_at`
- `details`

Potential check types:

- missing product reference
- negative sales quantity
- stale inventory data
- missing forecast
- duplicate sale record
- future timestamp

Why:

- Separates data validation from business anomaly detection.
- Supports data reliability and MLOps readiness.

---

### 9.2 Data Freshness Metrics

Future improvement:

Track freshness for key datasets.

Examples:

```text
now - InventorySnapshot.recorded_at
now - Sale.created_at
now - Forecast.generated_at
```

Potential alerts:

- inventory data older than expected threshold
- sales data ingestion delayed
- forecast not generated for required period

---

### 9.3 Ingestion Batch Tracking

Future entity:

```text
IngestionBatch
```

Possible fields:

- `id`
- `source_system`
- `dataset_name`
- `started_at`
- `finished_at`
- `status`
- `records_received`
- `records_failed`
- `error_message`

Why:

- Helps debug data pipeline problems.
- Supports observability and auditability.

---

## 10. MLOps Improvements

### 10.1 ModelVersion Entity

Future entity:

```text
ModelVersion
```

Possible fields:

- `id`
- `model_name`
- `version`
- `training_dataset_id`
- `created_at`
- `deployed_at`
- `status`
- `metrics`

Potential use cases:

- forecast generated by a specific model version
- anomaly generated by a specific detector version
- model rollback
- champion/challenger evaluation

---

### 10.2 Forecast Evaluation

Future improvement:

Extend `Forecast` with evaluation fields.

Possible fields:

- `actual_quantity`
- `error_value`
- `error_percentage`
- `error_metric`
- `evaluated_at`

Possible metrics:

- MAE
- MAPE
- RMSE
- bias

Why:

- Forecasts should not only be generated; they should be measured.

---

### 10.3 Prediction Intervals

Future improvement:

Extend forecast output with uncertainty.

Possible fields:

- `predicted_quantity`
- `lower_bound_quantity`
- `upper_bound_quantity`
- `confidence_level`

Why:

- Business users should understand forecast uncertainty.
- Stockout decisions should consider risk, not only point estimates.

---

### 10.4 Recommendation Feedback Loop

Future entity:

```text
RecommendationFeedback
```

Possible fields:

- `id`
- `recommendation_id`
- `user_id`
- `feedback_type`
- `comment`
- `created_at`

Examples:

- accepted
- rejected
- false_positive
- useful
- not_useful

Why:

- Supports learning from human decisions.
- Enables future model improvement and recommendation quality tracking.

---

### 10.5 Feature Store / Feature Set Metadata

Future entity:

```text
FeatureSet
```

Possible fields:

- `id`
- `name`
- `version`
- `created_at`
- `source_datasets`
- `description`

Why:

- Important when ML models become more serious.
- Helps explain which data was used for predictions.

---

## 11. Security and Access Control Improvements

### 11.1 Separate Domain User from Authentication User

Future improvement:

Separate business user profile from authentication credentials.

Possible split:

```text
User = domain identity and role in RetailOps
AuthAccount = login, password_hash, MFA, identity provider data
```

Why:

- Domain model should not become a full authentication system too early.
- Production systems often use external identity providers.

---

### 11.2 Password Hashing if Local Auth Is Added

If local authentication is ever added:

- Use `password_hash`, not encrypted password.
- Use a secure hashing algorithm such as Argon2 or bcrypt.
- Never store plaintext passwords.
- Never expose password hashes in API response models.

---

### 11.3 RBAC / ABAC

Future improvement:

Move beyond a simple `role` enum.

Possible entities:

- `Role`
- `Permission`
- `UserRole`
- `RolePermission`
- `Team`
- `Policy`

Possible rules:

- Category manager can see products in assigned categories.
- Inventory planner can manage stock alerts.
- Analyst can view anomalies and forecasts.
- Admin can manage users and roles.

---

### 11.4 Audit Log

Future entity:

```text
AuditLog
```

Possible fields:

- `id`
- `actor_user_id`
- `action`
- `resource_type`
- `resource_id`
- `timestamp`
- `request_id`
- `ip_address`

Why:

- Supports security review.
- Helps explain who changed what and when.

---

### 11.5 Multi-Tenant Isolation

Future improvement:

Add tenant or organization boundaries if the platform is used by multiple business units or customers.

Possible fields:

- `tenant_id`
- `organization_id`
- `business_unit_id`

Warning:

- Do not add multi-tenancy before it is clearly needed.
- It affects every table, API query, test and access-control rule.

---

## 12. Observability and Operations Improvements

### 12.1 Correlation and Trace IDs

Future fields:

- `correlation_id`
- `trace_id`
- `request_id`
- `ingestion_batch_id`

Why:

- Helps connect API requests, logs, data ingestion, alerts and user actions.
- Very useful for debugging and production operations.

---

### 12.2 Source System Tracking

Future fields:

- `source_system`
- `source_record_id`
- `source_timestamp`

Potential source systems:

- POS
- ERP
- WMS
- e-commerce platform
- marketplace integration

Why:

- Helps explain where data came from.
- Supports data lineage.

---

### 12.3 Domain Metrics

Future metrics:

- number of open alerts
- number of critical alerts
- average alert resolution time
- stale inventory percentage
- forecast coverage percentage
- recommendation acceptance rate
- false positive alert rate

Why:

- Makes the system measurable.
- Supports operational dashboards and portfolio evidence.

---

## 13. Event-Driven Architecture Improvements

### 13.1 Domain Events

Future event examples:

- `ProductCreated`
- `SaleRecorded`
- `InventorySnapshotReceived`
- `ForecastGenerated`
- `AnomalyDetected`
- `AlertCreated`
- `AlertAcknowledged`
- `RecommendationGenerated`
- `WorkflowActionPerformed`

Why:

- Prepares the system for Kafka/event-driven architecture.
- Makes data flow more scalable and decoupled.

---

### 13.2 Outbox Pattern

Future improvement:

Use the outbox pattern when combining database writes with event publishing.

Why:

- Prevents losing events when DB write succeeds but event publish fails.
- Common production pattern for reliable event-driven systems.

---

### 13.3 Idempotency

Future improvement:

Add idempotency keys for ingesting sales and inventory data.

Possible fields:

- `idempotency_key`
- `source_record_id`
- `ingestion_batch_id`

Why:

- Prevents duplicate sales or inventory snapshots when upstream systems retry requests.

---

## 14. Testing Improvements

### 14.1 Unit Tests for Pydantic Models

Future tests:

- valid product creation
- invalid empty SKU
- negative sale quantity rejected
- invalid inventory time order rejected
- dismiss action without comment rejected
- invalid forecast confidence rejected
- expired recommendation rejected

---

### 14.2 Contract Tests

Future improvement:

Test API request and response schemas against OpenAPI contracts.

Why:

- Prevents accidental breaking changes.
- Useful once frontend consumes backend APIs.

---

### 14.3 Property-Based Tests

Future improvement:

Use property-based testing for validators.

Example:

- generate random dates and verify time-order validation
- generate random quantities and prices
- generate status transitions and check workflow rules

Warning:

- Useful later, not needed for the first MVP commit.

---

### 14.4 Data Quality Tests

Future tests:

- sale must reference existing product
- forecast must reference existing product
- alert must reference existing product
- stale inventory should generate alert, not validation failure
- missing forecast should generate alert

---

### 14.5 Smoke Tests

Future smoke-test scenarios:

- API starts successfully.
- Health endpoint returns OK.
- Example product can be loaded.
- Example alert can be returned.
- Example workflow action can be created.

---

## 15. CI/CD Quality Gates

Future pipeline checks:

- formatting with Ruff or Black
- linting with Ruff
- typing with mypy or pyright
- unit tests with pytest
- coverage threshold
- OpenAPI schema generation check
- dependency vulnerability scan
- Docker image build
- container vulnerability scan

Potential advanced gates:

- OpenAPI diff check
- migration validation
- contract tests
- seed-data validation
- schema compatibility check for events

---

## 16. Documentation and ADR Improvements

### 16.1 ADR Candidates

Potential ADRs:

- Pydantic first, SQLAlchemy later.
- UUID as default identifier strategy.
- UTC datetime standard.
- Enum value naming convention.
- Alert vs Anomaly separation.
- WorkflowAction as audit trail.
- Recommendation linked optionally to Forecast, Anomaly and Alert.
- Channel as enum now, entity later.
- Supplier and Order as future domain extensions.
- Stale data as business alert, not validation error.

---

### 16.2 Diagrams

Future diagrams:

- MVP domain model diagram
- Alert workflow lifecycle diagram
- Data freshness and alert generation diagram
- Forecast-to-recommendation flow
- Domain events map
- Future enterprise data model expansion

---

## 17. FinOps and Data Volume Improvements

Future improvement:

Control data volume in local and cloud environments.

Possible policies:

- small synthetic seed data for local development
- larger demo dataset for portfolio presentation
- retention rules for historical sales and inventory snapshots
- archive old forecasts and resolved alerts
- avoid always-on expensive cloud services in early maturity stages

Why:

- Keeps MVP cost-aware.
- Aligns with local-first development strategy.

---

## 18. Recommended Near-Term Backlog Items

These are the best candidates for the next few tasks after the current model is committed:

| Priority | Improvement | Why it matters |
|---|---|---|
| P1 | Add unit tests for current Pydantic validators | Protects model quality |
| P1 | Add seed data for MVP scenarios | Enables demo and smoke tests |
| P1 | Add OpenAPI examples | Improves API usability |
| P1 | Add ADR for domain model decisions | Shows senior design thinking |
| P2 | Add Create/Read/Update API schemas | Prepares real API endpoints |
| P2 | Add SQLAlchemy models and Alembic | Enables real database persistence |
| P2 | Add workflow transition validation | Strengthens business process control |
| P3 | Add DataQualityCheck and ModelVersion | Prepares MLOps/data maturity |
| P3 | Add Order, Supplier, Promotion, PriceSnapshot | Expands enterprise retail scope |

---

## 19. Explicit Non-Goals for Current Sprint 3 Task

Do **not** implement the following now:

- full SQLAlchemy persistence layer
- Alembic migrations
- full RBAC model
- password/authentication system
- Order and Supplier entities
- Promotion and PriceSnapshot entities
- DataQualityCheck and ModelVersion entities
- Kafka/domain events
- outbox pattern
- multi-tenancy
- advanced MLOps model registry
- property-based testing
- enterprise-scale workflow engine

Reason:

The current Sprint 3 task is about defining a clean and understandable MVP domain model. Adding all advanced features now would reduce clarity and increase delivery risk.

---

## 20. Golden Principle

The most important design principle for this stage:

```text
Keep the MVP model simple enough to implement and test,
but explicit enough to show how the platform can evolve.
```

Good MVP design is not about adding every possible enterprise feature immediately. It is about creating a stable foundation that does not block future maturity.
