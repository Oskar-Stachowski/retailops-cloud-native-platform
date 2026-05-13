from fastapi.testclient import TestClient

from app.main import app
from app.api.metrics import render_api_info_metric

client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.metrics.stream_observability_service.render_prometheus_metrics",
        lambda: "# HELP retailops_stream_events_total Total stream events\n"
        "# TYPE retailops_stream_events_total counter\n"
        'retailops_stream_events_total{status="processed"} 3\n',
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "# HELP retailops_api_info RetailOps API service information." in response.text
    assert 'retailops_api_info{environment="local",service="retailops-api"} 1.0' in response.text
    assert 'retailops_stream_events_total{status="processed"} 3' in response.text


def test_api_info_metric_escapes_environment_label(monkeypatch) -> None:
    monkeypatch.setattr("app.api.metrics.settings.app_env", 'local"dev\\stage\nnext')

    output = render_api_info_metric()

    assert '# HELP retailops_api_info RetailOps API service information.' in output
    assert 'environment="local\\"dev\\\\stage\\nnext"' in output
