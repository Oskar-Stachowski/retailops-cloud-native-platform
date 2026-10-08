"""Run the dedicated v2 consumer; never subscribe the legacy no-op handlers to v2."""

from app.core.config import settings
from app.services.intelligence_consumer import IntelligenceEventConsumer
from app.services.intelligence_contract import TOPIC
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
    build_confluent_kafka_consumer,
    build_signal_stop_event,
)


def main() -> int:
    if not settings.broker_bootstrap_servers:
        msg = "RETAILOPS_BROKER_BOOTSTRAP_SERVERS is required"
        raise RuntimeError(msg)
    config = RealtimeConsumerRunnerConfig(
        bootstrap_servers=settings.broker_bootstrap_servers,
        group_id="retailops-intelligence-v2",
        client_id="retailops-intelligence-v2",
        topics=(TOPIC,),
    )
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=build_confluent_kafka_consumer(config),
        event_consumer=IntelligenceEventConsumer(),
        config=config,
    )
    runner.run(stop_event=build_signal_stop_event())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
