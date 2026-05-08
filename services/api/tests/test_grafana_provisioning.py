import json
from pathlib import Path


OBSERVABILITY_PATH = Path(__file__).resolve().parents[3] / "observability"
DATASOURCE_PATH = (
    OBSERVABILITY_PATH / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
)
DASHBOARD_PROVIDER_PATH = (
    OBSERVABILITY_PATH / "grafana" / "provisioning" / "dashboards" / "retailops.yml"
)
DASHBOARD_PATH = (
    OBSERVABILITY_PATH / "grafana" / "dashboards" / "retailops-overview.json"
)


def test_grafana_prometheus_datasource_is_provisioned() -> None:
    datasource = DATASOURCE_PATH.read_text(encoding="utf-8")

    assert "name: RetailOps Prometheus" in datasource
    assert "uid: retailops-prometheus" in datasource
    assert "type: prometheus" in datasource
    assert "url: http://prometheus:9090" in datasource
    assert "isDefault: true" in datasource


def test_grafana_dashboard_provider_loads_local_dashboards() -> None:
    provider = DASHBOARD_PROVIDER_PATH.read_text(encoding="utf-8")

    assert "name: RetailOps" in provider
    assert "type: file" in provider
    assert "path: /var/lib/grafana-dashboards" in provider


def test_retailops_overview_dashboard_contains_core_stream_panels() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    expressions = {
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    }
    dashboard_json = json.dumps(dashboard)

    assert dashboard["uid"] == "retailops-overview"
    assert dashboard["title"] == "RetailOps Overview"
    assert "retailops-prometheus" in dashboard_json
    assert "API Target Up" in panel_titles
    assert "Stream Events" in panel_titles
    assert "Processing Latency" in panel_titles
    assert "Consumer Lag" in panel_titles
    assert 'up{job="retailops-api"}' in expressions
    assert "retailops_stream_events_total" in expressions
    assert "retailops_stream_processing_latency_seconds_avg" in expressions
    assert "retailops_stream_consumer_lag_events" in expressions
