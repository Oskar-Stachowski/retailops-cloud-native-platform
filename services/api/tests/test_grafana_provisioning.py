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
API_DASHBOARD_PATH = (
    OBSERVABILITY_PATH / "grafana" / "dashboards" / "retailops-api.json"
)
BUSINESS_DASHBOARD_PATH = (
    OBSERVABILITY_PATH
    / "grafana"
    / "dashboards"
    / "retailops-business-operations.json"
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
    assert "retailops_stream_events_total or vector(0)" in expressions
    assert "retailops_stream_processing_latency_seconds_avg" in expressions
    assert "retailops_stream_consumer_lag_events or vector(0)" in expressions


def test_retailops_api_dashboard_contains_api_and_db_panels() -> None:
    dashboard = json.loads(API_DASHBOARD_PATH.read_text(encoding="utf-8"))
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    expressions = {
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    }
    dashboard_json = json.dumps(dashboard)

    assert dashboard["uid"] == "retailops-api"
    assert dashboard["title"] == "RetailOps API"
    assert "retailops-prometheus" in dashboard_json
    assert "API Target" in panel_titles
    assert "API Info" in panel_titles
    assert "DB Operations" in panel_titles
    assert "DB Operation Duration Max" in panel_titles
    assert "Metrics Generation" in panel_titles
    assert 'up{job="retailops-api"}' in expressions
    assert "retailops_api_info" in expressions
    assert "retailops_db_operations_total or vector(0)" in expressions
    assert "retailops_db_operation_duration_seconds_max or vector(0)" in expressions
    assert "retailops_stream_metrics_generated_at_seconds" in expressions


def test_retailops_business_operations_dashboard_contains_operational_panels() -> None:
    dashboard = json.loads(BUSINESS_DASHBOARD_PATH.read_text(encoding="utf-8"))
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    expressions = {
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    }
    dashboard_json = json.dumps(dashboard)

    assert dashboard["uid"] == "retailops-business-operations"
    assert dashboard["title"] == "RetailOps Business Operations"
    assert "retailops-prometheus" in dashboard_json
    assert "Stream Active" in panel_titles
    assert "Event Freshness" in panel_titles
    assert "Processed Events" in panel_titles
    assert "Dead Letter Events" in panel_titles
    assert "Operational Events by Type" in panel_titles
    assert "Event Processing Status" in panel_titles
    assert "Processing Latency" in panel_titles
    assert "Consumer Throughput" in panel_titles
    assert "retailops_stream_latest_event_present" in expressions
    assert "retailops_stream_event_freshness_seconds" in expressions
    assert "retailops_stream_processed_event_total" in expressions
    assert "retailops_stream_dlq_events_total or vector(0)" in expressions
    assert "retailops_stream_events_by_type_total or vector(0)" in expressions
    assert "retailops_stream_events_total or vector(0)" in expressions
    assert "retailops_stream_processing_latency_seconds_avg" in expressions
    assert "retailops_stream_processing_latency_seconds_max" in expressions
    assert "retailops_stream_consumer_received_events_total or vector(0)" in expressions
    assert "retailops_stream_consumer_processed_events_total or vector(0)" in expressions
    assert "retailops_stream_consumer_failed_events_total or vector(0)" in expressions
