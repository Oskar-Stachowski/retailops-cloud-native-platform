# Demand Forecast Feature Dataset Contract

This contract defines the first Sprint 12 MLOps handoff: a stable feature
dataset shape for demand forecasting. It does not implement feature generation,
training, inference, model registry, or drift monitoring.

## Dataset

| Field | Value |
| --- | --- |
| Dataset name | `retailops-demand-forecast-features` |
| Schema version | `1.0` |
| Row schema | `demand_forecast_features.schema.json` |
| Manifest schema | `demand_forecast_feature_manifest.schema.json` |
| Recommended path | `data/synthetic/<profile>/features/demand_forecast/` |
| Grain | `date`, `product_id`, `store_id`, `channel` |
| Forecast target | `units_sold` |

Each row represents observed demand for one product in one store and channel on
one business date. The feature job should write a manifest next to the dataset
so later training and evaluation reports can reference an immutable dataset ID.

## Required Feature Groups

| Group | Required fields |
| --- | --- |
| Lineage | `schema_version`, `dataset_id`, `feature_row_id`, `generated_at` |
| Grain | `date`, `product_id`, `store_id`, `channel` |
| Target | `units_sold` |
| Sales and price | `sales_revenue`, `unit_price`, `discount_percent` |
| Promotion | `promotion_active` |
| Inventory | `stockout_flag`, `inventory_on_hand` |
| Product metadata | `category`, `brand` |
| Calendar | `day_of_week`, `is_weekend` |

Optional fields such as `latent_units_demand`, `promotion_type`,
`inventory_reserved`, `product_status`, `week_of_year`, `month`, and
`data_quality_status` are included in the schema so the next feature-generation
commit can expose richer signals without changing the contract version.

## Source Mapping

| Source artifact | Contract use |
| --- | --- |
| `sales.csv` | Target, revenue, channel and observed sales date. |
| `products.csv` | Product category, brand and status attributes. |
| `stores.csv` | Store identifier and future regional features. |
| `price_history.csv` | Effective unit price and discount calculations. |
| `promotions.csv` | Promotion activity and promotion type flags. |
| `inventory_snapshots.csv` | Stock availability and stockout features. |

## Compatibility Rules

- `schema_version` must stay `1.0` for additive optional fields.
- Removing a field, changing a required field type, changing the grain, or
  changing the target requires a new schema version.
- Feature rows must be deterministic for the same source dataset and seed.
- Training jobs must reference `dataset_id`, `schema_version`, source artifacts,
  and the feature manifest in their evaluation reports.
- Generated feature datasets larger than tiny examples should stay out of Git.

## Examples

- `demand_forecast_features.example.jsonl`
- `demand_forecast_feature_manifest.example.json`
