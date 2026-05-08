from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_text(monkeypatch):
    monkeypatch.setattr(
        "app.api.metrics.stream_observability_service.render_prometheus_metrics",
        lambda: "# HELP retailops_stream_events_total Total stream events\n"
        "# TYPE retailops_stream_events_total counter\n"
        'retailops_stream_events_total{status="processed"} 3\n',
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/plain; version=0.0.4"
    )
    assert "# HELP retailops_api_info RetailOps API service information." in response.text
    assert (
        'retailops_api_info{service="retailops-api",environment="local"} 1'
        in response.text
    )
    assert 'retailops_stream_events_total{status="processed"} 3' in response.text
