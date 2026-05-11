from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository


@dataclass(frozen=True)
class PrometheusMetric:
    name: str
    help_text: str
    metric_type: str
    value: float
    labels: dict[str, str] | None = None


class StreamObservabilityService:
    def __init__(
        self,
        repository: RealtimeMetricsRepository | None = None,
    ) -> None:
        self.repository = repository or RealtimeMetricsRepository()

    def render_prometheus_metrics(self) -> str:
        metrics = self.repository.get_stream_processing_metrics()
        lines: list[str] = []

        for metric in self._build_metrics(metrics):
            lines.extend(self._render_metric(metric))

        return "\n".join(lines) + "\n"

    def _build_metrics(self, metrics: dict[str, Any]) -> list[PrometheusMetric]:
        event_status_counts = metrics.get("event_status_counts") or []
        event_type_counts = metrics.get("event_type_counts") or []
        freshness = metrics.get("freshness") or {}
        latency = metrics.get("processing_latency") or {}
        consumer_states = metrics.get("consumer_states") or []

        output: list[PrometheusMetric] = [
            PrometheusMetric(
                name="retailops_stream_latest_event_present",
                help_text=(
                    "Whether at least one stream event has been ingested, "
                    "represented as 1 or 0."
                ),
                metric_type="gauge",
                value=1 if freshness.get("latest_event_at") else 0,
            ),
            PrometheusMetric(
                name="retailops_stream_event_freshness_seconds",
                help_text="Age of the latest ingested stream event in seconds.",
                metric_type="gauge",
                value=self._number_or_zero(freshness.get("freshness_seconds")),
            ),
            PrometheusMetric(
                name="retailops_stream_processing_latency_seconds_avg",
                help_text="Average stream event processing latency in seconds.",
                metric_type="gauge",
                value=self._number_or_zero(latency.get("avg_latency_seconds")),
            ),
            PrometheusMetric(
                name="retailops_stream_processing_latency_seconds_max",
                help_text="Maximum stream event processing latency in seconds.",
                metric_type="gauge",
                value=self._number_or_zero(latency.get("max_latency_seconds")),
            ),
            PrometheusMetric(
                name="retailops_stream_processed_event_total",
                help_text="Total processed stream events with latency measurements.",
                metric_type="counter",
                value=self._number_or_zero(latency.get("processed_event_count")),
            ),
        ]

        for row in event_status_counts:
            status = str(row.get("status") or "unknown")
            count = self._number_or_zero(row.get("event_count"))
            output.append(
                PrometheusMetric(
                    name="retailops_stream_events_total",
                    help_text="Total stream events by processing status.",
                    metric_type="counter",
                    value=count,
                    labels={"status": status},
                ),
            )

            if status == "failed_dead_lettered":
                output.append(
                    PrometheusMetric(
                        name="retailops_stream_dlq_events_total",
                        help_text="Total stream events routed to the dead-letter path.",
                        metric_type="counter",
                        value=count,
                    ),
                )

        output.extend(
            PrometheusMetric(
                name="retailops_stream_events_by_type_total",
                help_text="Total stream events by event type.",
                metric_type="counter",
                value=self._number_or_zero(row.get("event_count")),
                labels={"event_type": str(row.get("event_type") or "unknown")},
            )
            for row in event_type_counts
        )

        for row in consumer_states:
            consumer_name = str(row.get("consumer_name") or "unknown")
            labels = {"consumer": consumer_name}
            received = self._number_or_zero(row.get("received_events"))
            processed = self._number_or_zero(row.get("processed_events"))
            failed = self._number_or_zero(row.get("failed_events"))
            ignored = self._number_or_zero(row.get("ignored_events"))
            dead_lettered = self._number_or_zero(row.get("dead_lettered_events"))

            output.extend(
                [
                    PrometheusMetric(
                        name="retailops_stream_consumer_running",
                        help_text="Consumer running state, represented as 1 or 0.",
                        metric_type="gauge",
                        value=1 if row.get("running") else 0,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_received_events_total",
                        help_text="Total events received by consumer.",
                        metric_type="counter",
                        value=received,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_processed_events_total",
                        help_text="Total events processed by consumer.",
                        metric_type="counter",
                        value=processed,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_failed_events_total",
                        help_text="Total events failed by consumer.",
                        metric_type="counter",
                        value=failed,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_ignored_events_total",
                        help_text="Total duplicate or ignored events by consumer.",
                        metric_type="counter",
                        value=ignored,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_dlq_events_total",
                        help_text="Total dead-lettered events by consumer.",
                        metric_type="counter",
                        value=dead_lettered,
                        labels=labels,
                    ),
                    PrometheusMetric(
                        name="retailops_stream_consumer_lag_events",
                        help_text="Consumer lag proxy based on received minus processed events.",
                        metric_type="gauge",
                        value=max(received - processed - ignored - failed, 0),
                        labels=labels,
                    ),
                ],
            )

        output.append(
            PrometheusMetric(
                name="retailops_stream_metrics_generated_at_seconds",
                help_text="Unix timestamp when stream metrics were rendered.",
                metric_type="gauge",
                value=datetime.now(UTC).timestamp(),
            ),
        )

        return output

    def _render_metric(self, metric: PrometheusMetric) -> list[str]:
        label_text = self._render_labels(metric.labels or {})
        return [
            f"# HELP {metric.name} {metric.help_text}",
            f"# TYPE {metric.name} {metric.metric_type}",
            f"{metric.name}{label_text} {self._format_number(metric.value)}",
        ]

    def _render_labels(self, labels: dict[str, str]) -> str:
        if not labels:
            return ""

        rendered = ",".join(
            f'{key}="{self._escape_label_value(value)}"' for key, value in sorted(labels.items())
        )
        return f"{{{rendered}}}"

    def _escape_label_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    def _number_or_zero(self, value: object) -> float:
        if value in (None, ""):
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _format_number(self, value: float) -> str:
        number = float(value)
        if number.is_integer():
            return str(int(number))

        return f"{number:.6f}".rstrip("0").rstrip(".")
