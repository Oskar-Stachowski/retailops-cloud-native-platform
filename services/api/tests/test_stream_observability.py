from app.services.stream_observability import StreamObservabilityService


class FakeRealtimeMetricsRepository:
    def get_stream_processing_metrics(self):
        return {
            "event_status_counts": [
                {"status": "processed", "event_count": 12},
                {"status": "failed_dead_lettered", "event_count": 2},
            ],
            "event_type_counts": [
                {"event_type": "sale_completed", "event_count": 9},
                {"event_type": "alert_created", "event_count": 3},
            ],
            "freshness": {
                "freshness_seconds": 42.5,
            },
            "processing_latency": {
                "processed_event_count": 12,
                "avg_latency_seconds": 0.25,
                "max_latency_seconds": 1.5,
            },
            "consumer_states": [
                {
                    "consumer_name": "retailops-realtime-consumer",
                    "running": True,
                    "received_events": 16,
                    "processed_events": 12,
                    "failed_events": 2,
                    "dead_lettered_events": 2,
                    "ignored_events": 1,
                }
            ],
        }


def test_stream_observability_renders_prometheus_metrics() -> None:
    service = StreamObservabilityService(
        repository=FakeRealtimeMetricsRepository(),
    )

    output = service.render_prometheus_metrics()

    assert "# HELP retailops_stream_events_total" in output
    assert 'retailops_stream_events_total{status="processed"} 12' in output
    assert "retailops_stream_dlq_events_total 2" in output
    assert (
        'retailops_stream_events_by_type_total{event_type="sale_completed"} 9'
        in output
    )
    assert "retailops_stream_event_freshness_seconds 42.5" in output
    assert "retailops_stream_processing_latency_seconds_avg 0.25" in output
    assert (
        'retailops_stream_consumer_lag_events{consumer="retailops-realtime-consumer"} 1'
        in output
    )
