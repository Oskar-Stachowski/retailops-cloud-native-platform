"""Private stdin-only child for a real kill after broker delivery/before SQL commit."""

import json
import sys
import time

from app.services.source_observation_broker import BrokerConfig, build_producer
from app.services.source_observation_outbox import (
    ObservationOutbox,
    ObservationPublisher,
)


def delivered():
    sys.stdout.write("DELIVERED\n")
    sys.stdout.flush()
    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        settings = json.loads(sys.stdin.buffer.readline(32768))
        config = BrokerConfig.model_validate_json(json.dumps(settings["broker"]))
        producer, topology = build_producer(config)
        publisher = ObservationPublisher(
            ObservationOutbox(settings["database"]),
            producer,
            topology,
            after_delivery=delivered,
        )
        publisher.once()
        raise RuntimeError
    except Exception:
        sys.stderr.write("source_observation_child_unavailable\n")
        sys.exit(2)
