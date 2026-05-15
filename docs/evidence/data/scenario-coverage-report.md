# RetailOps scenario coverage report

Generated at: `2026-05-14T07:17:25.739867+00:00`
Data directory: `data/demo`
Status: **PASSED**

## Checks

| Check | Status | Evidence |
| --- | --- | --- |
| `sales_drop_present` | `passed` | anomalies.anomaly_type and alerts.alert_type |
| `sales_spike_present` | `passed` | anomalies.anomaly_type |
| `stale_inventory_present` | `passed` | anomalies.anomaly_type |
| `stockout_risk_present` | `passed` | alerts.alert_type or recommendations.rationale |
| `overstock_risk_present` | `passed` | alerts.alert_type |
| `missing_forecast_context_present` | `passed` | products without forecast rows |
| `inventory_freshness_context_present` | `passed` | inventory_snapshots.recorded_at and ingested_at |

## Scenario counts

### Anomaly types

| Type | Count |
| --- | ---: |
| `sales_drop` | 2 |
| `sales_spike` | 1 |
| `stale_inventory` | 1 |

### Alert types

| Type | Count |
| --- | ---: |
| `overstock_risk` | 1 |
| `sales_drop` | 2 |
| `stockout_risk` | 1 |

### Recommendation types

| Type | Count |
| --- | ---: |
| `investigate_sales_drop` | 1 |
| `refresh_inventory_data` | 1 |
| `replenish_stock` | 1 |
| `review_price` | 1 |

## Missing forecast context

Products without forecast rows: `2`

This is intentional demo evidence for UI/API paths that must handle products without forecasts.

## Claim boundary

Safe claim: the demo dataset contains deterministic operational scenarios for sales drops, sales spikes, stale inventory, stockout risk, overstock risk and products without forecasts.

Careful claim: this does not mean every production data-quality edge case is modeled; it is a portfolio readiness gate for representative retail operations scenarios.
