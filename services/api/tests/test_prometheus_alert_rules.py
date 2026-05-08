from pathlib import Path


RULES_PATH = (
    Path(__file__).resolve().parents[3]
    / "observability"
    / "prometheus"
    / "rules"
    / "stream-alerts.yml"
)
API_RULES_PATH = (
    Path(__file__).resolve().parents[3]
    / "observability"
    / "prometheus"
    / "rules"
    / "api-alerts.yml"
)


def test_stream_alert_rules_cover_core_realtime_failure_modes() -> None:
    rules = RULES_PATH.read_text(encoding="utf-8")

    expected_alerts = {
        "RetailOpsApiMetricsTargetDown",
        "RetailOpsStreamNoEventsIngested",
        "RetailOpsStreamEventsStale",
        "RetailOpsStreamDeadLetterEventsIncreasing",
        "RetailOpsStreamConsumerFailuresIncreasing",
        "RetailOpsStreamConsumerLagHigh",
        "RetailOpsStreamConsumerLagCritical",
        "RetailOpsStreamConsumerDown",
        "RetailOpsStreamConsumerMissing",
        "RetailOpsStreamProcessingLatencyHigh",
        "RetailOpsStreamProcessingLatencyCritical",
    }

    for alert_name in expected_alerts:
        assert f"alert: {alert_name}" in rules

    expected_metrics = {
        "retailops_stream_latest_event_present",
        "retailops_stream_event_freshness_seconds",
        "retailops_stream_dlq_events_total",
        "retailops_stream_consumer_failed_events_total",
        "retailops_stream_consumer_lag_events",
        "retailops_stream_consumer_running",
        "retailops_stream_processing_latency_seconds_avg",
        "retailops_stream_processing_latency_seconds_max",
    }

    for metric_name in expected_metrics:
        assert metric_name in rules


def test_api_alert_rules_cover_platform_and_database_failure_modes() -> None:
    rules = API_RULES_PATH.read_text(encoding="utf-8")

    expected_alerts = {
        "RetailOpsPrometheusTargetDown",
        "RetailOpsApiInfoMissing",
        "RetailOpsDatabaseOperationsMissing",
        "RetailOpsDatabaseErrorsIncreasing",
        "RetailOpsDatabaseLatencyHigh",
        "RetailOpsDatabaseLatencyCritical",
    }

    for alert_name in expected_alerts:
        assert f"alert: {alert_name}" in rules

    expected_metrics = {
        'up{job="prometheus"}',
        "retailops_api_info",
        "retailops_db_operations_total",
        "retailops_db_operation_duration_seconds_max",
    }

    for metric_name in expected_metrics:
        assert metric_name in rules
