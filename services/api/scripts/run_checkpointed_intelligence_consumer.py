"""Run or inspect the explicit, private, checkpointed intelligence lane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg
from confluent_kafka import KafkaException

from app.services.intelligence_checkpoint import CheckpointError
from app.services.intelligence_checkpoint_runner import (
    CheckpointBrokerConfig,
    IntelligenceCheckpointRunner,
    build_checkpoint_client,
)
from app.services.realtime_consumer_runner import build_signal_stop_event


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-config", type=Path, required=True)
    parser.add_argument("--group-id", default="retailops-intelligence-v2-checkpointed")
    parser.add_argument("--bootstrap-retained-log", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    try:
        configuration = CheckpointBrokerConfig.read_private(args.broker_config)
    except (OSError, ValueError):
        sys.stdout.write(
            json.dumps({"status": "error", "code": "private_broker_configuration_invalid"}) + "\n"
        )
        return 2
    client = None
    try:
        client, topology = build_checkpoint_client(configuration, args.group_id)
        runner = IntelligenceCheckpointRunner(
            kafka_consumer=client,
            topology=topology,
            group=args.group_id,
            bootstrap=args.bootstrap_retained_log,
        )
        if args.status:
            sys.stdout.write(json.dumps(runner.status(), sort_keys=True) + "\n")
        else:
            try:
                runner.run(stop_event=build_signal_stop_event())
            finally:
                client = None  # run() owns closing the client, including on failure
            sys.stdout.write(json.dumps({"status": "stopped"}) + "\n")
    except CheckpointError as exc:
        sys.stdout.write(json.dumps({"status": "error", "code": str(exc)}) + "\n")
        return 3
    except (psycopg.Error, RuntimeError, KafkaException, OSError):
        sys.stdout.write(
            json.dumps({"status": "error", "code": "intelligence_transport_unavailable"}) + "\n"
        )
        return 4
    finally:
        if client is not None:
            client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
