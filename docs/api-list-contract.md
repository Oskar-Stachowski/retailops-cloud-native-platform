# Backend API list contract

## Standard contract

Business collection endpoints should expose:

```json
{
  "items": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 125
  }
}
```

Required pagination parameters:

- `limit`: minimum `1`, default `50`, maximum endpoint-specific but not above `200` for current local API checks.
- `offset`: minimum `0`, default `0`.

Recommended sorting parameters for durable business collections:

- `sort_by`
- `sort_order` with `asc` or `desc`

## Endpoint status

| Endpoint | Pagination | Sorting | Notes |
|---|---:|---:|---|
| `GET /products` | yes | yes | Product filters: category, status, search. |
| `GET /forecasts` | yes | yes | Product/status/method/date filters. |
| `GET /forecast-runs` | yes | yes | MLOps metadata filters. |
| `GET /inventory-snapshots` | yes | yes | Product, warehouse, unit and date filters. |
| `GET /sales` | yes | yes | Product, channel, currency and date filters. |
| `GET /inventory-risks` | yes | yes | Risk status and category filters. |
| `GET /notifications` | yes | no | Small demo list; now exposes pagination metadata. |

Dashboard and analytics widget endpoints may use endpoint-specific `limit` parameters because they are not generic collection APIs.

## Validation

```bash
cd services/api
PYTHONPATH=. pytest tests/test_api_list_contract_readiness.py tests/test_notifications_api.py
```

Safe portfolio wording after tests pass:

> Standardized API list contracts across key Backend endpoints with pagination, filters, sorting metadata and OpenAPI-backed contract tests.
