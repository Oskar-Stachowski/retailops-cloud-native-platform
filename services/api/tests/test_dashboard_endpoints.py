from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def sample_summary() -> dict:
    return {
        "products_count": 3,
        "sales_count": 12,
        "inventory_snapshots_count": 6,
        "forecasts_count": 2,
        "anomalies_count": 1,
        "recommendations_count": 1,
        "open_anomalies_count": 1,
        "open_recommendations_count": 1,
        "open_work_items_count": 2,
        "last_refresh_at": "2026-05-01T10:00:00+00:00",
    }


def sample_sales_trend() -> list[dict]:
    return [
        {
            "date": "2026-05-01",
            "units_sold": 10,
            "revenue": 199.90,
        },
        {
            "date": "2026-05-02",
            "units_sold": 15,
            "revenue": 299.50,
        },
    ]


def sample_work_item(source: str = "anomaly") -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "source": source,
        "product_id": "22222222-2222-2222-2222-222222222222",
        "sku": "ELEC-HEAD-001",
        "type": "stockout_risk",
        "severity": "high",
        "priority": "high",
        "status": "open",
        "title": "Potential stockout risk",
        "description": "Forecast demand is higher than current stock.",
        "created_at": "2026-05-01T10:00:00+00:00",
        "updated_at": "2026-05-01T11:00:00+00:00",
        "detected_at": "2026-05-01T09:30:00+00:00",
    }


def sample_stock_risk_summary() -> dict:
    return {
        "total_risk_items": 4,
        "normal_count": 1,
        "stockout_risk_count": 2,
        "overstock_risk_count": 1,
        "unknown_count": 0,
    }


def sample_live_operations() -> dict:
    return {
        "generated_at": "2026-05-01T12:00:00+00:00",
        "window_minutes": 15,
        "metrics": {
            "revenue": 499.40,
            "units_sold": 25,
            "orders_created": 9,
            "sales_events": 12,
            "return_amount": 39.90,
            "return_units": 1,
            "stock_delta": -7,
            "stock_events": 3,
            "replenishment_units": 50,
            "anomalies_detected": 1,
            "alerts_created": 1,
            "workflow_actions": 2,
            "raw_metrics": {
                "live_revenue": {
                    "value": 499.40,
                    "observation_count": 12,
                    "latest_observed_at": "2026-05-01T11:59:00+00:00",
                }
            },
        },
        "event_status_counts": {
            "received": 0,
            "processed": 15,
            "failed_dead_lettered": 1,
            "ignored_duplicate": 2,
            "total": 18,
        },
        "freshness": {
            "latest_event_at": "2026-05-01T11:59:00+00:00",
            "freshness_seconds": 42,
            "is_fresh": True,
        },
        "recent_events": [
            {
                "event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV2",
                "event_type": "sale_completed",
                "topic": "retailops.sales.v1",
                "status": "processed",
                "occurred_at": "2026-05-01T11:58:59+00:00",
                "ingested_at": "2026-05-01T11:59:00+00:00",
                "processed_at": "2026-05-01T11:59:01+00:00",
                "error_message": None,
            }
        ],
        "alerts": [
            {
                "event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV3",
                "event_type": "alert_created",
                "status": "processed",
                "occurred_at": "2026-05-01T11:57:00+00:00",
                "ingested_at": "2026-05-01T11:57:01+00:00",
                "product_id": "22222222-2222-2222-2222-222222222222",
                "severity": "high",
                "title": "Potential stockout risk",
                "payload": {"severity": "high"},
            }
        ],
        "consumer_states": [
            {
                "consumer_name": "retailops-realtime-consumer",
                "running": True,
                "received_events": 18,
                "processed_events": 15,
                "failed_events": 1,
                "dead_lettered_events": 1,
                "ignored_events": 2,
                "last_event_id": "01HXZ7M8E5K9Q3Q76W7J7Y5YV2",
                "last_event_type": "sale_completed",
                "last_error": None,
                "last_processed_at": "2026-05-01T11:59:01+00:00",
                "started_at": "2026-05-01T11:00:00+00:00",
                "stopped_at": None,
                "updated_at": "2026-05-01T11:59:01+00:00",
            }
        ],
        "limits": {
            "recent_events": 5,
            "alerts": 3,
        },
    }


def test_dashboard_summary_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_summary",
        lambda: {"summary": sample_summary()},
    )

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()

    assert "summary" in payload
    assert payload["summary"]["products_count"] == 3
    assert payload["summary"]["sales_count"] == 12
    assert payload["summary"]["inventory_snapshots_count"] == 6
    assert payload["summary"]["open_work_items_count"] == 2
    assert payload["summary"]["last_refresh_at"] == "2026-05-01T10:00:00Z"


def test_dashboard_sales_trend_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_sales_trend",
        lambda days=14: {
            "items": sample_sales_trend(),
            "days": days,
        },
    )

    response = client.get("/dashboard/sales-trend?days=7")

    assert response.status_code == 200
    payload = response.json()

    assert payload["days"] == 7
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["date"] == "2026-05-01"
    assert payload["items"][0]["units_sold"] == 10
    assert payload["items"][0]["revenue"] == 199.90


def test_dashboard_sales_trend_endpoint_rejects_invalid_days():
    response = client.get("/dashboard/sales-trend?days=0")

    assert response.status_code == 422


def test_dashboard_alerts_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_open_alerts",
        lambda limit=10: {
            "items": [sample_work_item(source="anomaly")],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/alerts?limit=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 5
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["source"] == "anomaly"
    assert payload["items"][0]["status"] == "open"


def test_dashboard_alerts_endpoint_rejects_invalid_limit():
    response = client.get("/dashboard/alerts?limit=101")

    assert response.status_code == 422


def test_dashboard_recommendations_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_top_recommendations",
        lambda limit=10: {
            "items": [sample_work_item(source="recommendation")],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/recommendations?limit=5")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 5
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["source"] == "recommendation"


def test_dashboard_open_work_items_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_open_work_items",
        lambda limit=10: {
            "items": [
                sample_work_item(source="anomaly"),
                sample_work_item(source="recommendation"),
            ],
            "limit": limit,
        },
    )

    response = client.get("/dashboard/open-work-items?limit=2")

    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["source"] in {"anomaly", "recommendation"}


def test_dashboard_stock_risk_summary_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_stock_risk_summary",
        lambda: sample_stock_risk_summary(),
    )

    response = client.get("/dashboard/stock-risk-summary")

    assert response.status_code == 200
    payload = response.json()

    assert payload["total_risk_items"] == 4
    assert payload["normal_count"] == 1
    assert payload["stockout_risk_count"] == 2
    assert payload["overstock_risk_count"] == 1
    assert payload["unknown_count"] == 0


def test_dashboard_operational_visibility_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_operational_visibility",
        lambda sales_trend_days=14, work_items_limit=10: {
            "generated_at": "2026-05-01T12:00:00+00:00",
            "summary": sample_summary(),
            "stock_risk_summary": sample_stock_risk_summary(),
            "sales_trend": sample_sales_trend(),
            "open_work_items": [
                sample_work_item(source="anomaly"),
                sample_work_item(source="recommendation"),
            ],
            "limits": {
                "sales_trend_days": sales_trend_days,
                "work_items_limit": work_items_limit,
            },
        },
    )

    response = client.get(
        "/dashboard/operational-visibility?"
        "sales_trend_days=7&work_items_limit=2"
    )

    assert response.status_code == 200
    payload = response.json()

    assert "generated_at" in payload
    assert payload["summary"]["products_count"] == 3
    assert payload["stock_risk_summary"]["stockout_risk_count"] == 2
    assert len(payload["sales_trend"]) == 2
    assert len(payload["open_work_items"]) == 2
    assert payload["limits"]["sales_trend_days"] == 7
    assert payload["limits"]["work_items_limit"] == 2


def test_dashboard_operational_visibility_endpoint_rejects_invalid_params():
    response = client.get(
        "/dashboard/operational-visibility?"
        "sales_trend_days=0&work_items_limit=10"
    )

    assert response.status_code == 422


def test_dashboard_live_operations_endpoint_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        "app.api.dashboard.dashboard_service.get_live_operations",
        lambda window_minutes=15, recent_events_limit=20, alerts_limit=10: {
            **sample_live_operations(),
            "window_minutes": window_minutes,
            "limits": {
                "recent_events": recent_events_limit,
                "alerts": alerts_limit,
            },
        },
    )

    response = client.get(
        "/dashboard/live-operations?"
        "window_minutes=15&recent_events_limit=5&alerts_limit=3"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["window_minutes"] == 15
    assert payload["metrics"]["revenue"] == 499.40
    assert payload["event_status_counts"]["failed_dead_lettered"] == 1
    assert payload["freshness"]["is_fresh"] is True
    assert payload["recent_events"][0]["event_type"] == "sale_completed"
    assert payload["alerts"][0]["severity"] == "high"
    assert payload["consumer_states"][0]["consumer_name"] == (
        "retailops-realtime-consumer"
    )
    assert payload["limits"]["recent_events"] == 5
    assert payload["limits"]["alerts"] == 3


def test_dashboard_live_operations_endpoint_rejects_invalid_params():
    response = client.get(
        "/dashboard/live-operations?"
        "window_minutes=0&recent_events_limit=20&alerts_limit=10"
    )

    assert response.status_code == 422
