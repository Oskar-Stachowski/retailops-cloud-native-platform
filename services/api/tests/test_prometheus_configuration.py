from pathlib import Path

PROMETHEUS_CONFIG_PATH = Path(__file__).resolve().parents[3] / "observability" / "prometheus.yml"


def test_prometheus_config_scrapes_api_metrics_endpoint() -> None:
    config = PROMETHEUS_CONFIG_PATH.read_text(encoding="utf-8")

    assert "scrape_interval: 15s" in config
    assert "evaluation_interval: 15s" in config
    assert "job_name: retailops-api" in config
    assert "metrics_path: /metrics" in config
    assert "api:8000" in config
    assert "service: retailops-api" in config


def test_prometheus_config_loads_local_alert_rules() -> None:
    config = PROMETHEUS_CONFIG_PATH.read_text(encoding="utf-8")

    assert "rule_files:" in config
    assert "/etc/prometheus/rules/*.yml" in config


def test_prometheus_config_includes_local_observability_labels() -> None:
    config = PROMETHEUS_CONFIG_PATH.read_text(encoding="utf-8")

    assert "external_labels:" in config
    assert "environment: local" in config
    assert "platform: retailops" in config
    assert "job_name: prometheus" in config
    assert "prometheus:9090" in config
