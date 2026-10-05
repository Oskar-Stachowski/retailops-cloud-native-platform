"""Append native observation versions or publish a bounded durable outbox."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr

from app.services.source_observation_broker import BrokerConfig, build_producer
from app.services.source_observation_outbox import (
    ObservationOutbox,
    ObservationPublisher,
    private_bytes,
)
from app.services.source_observation_wire import ObservationVersion


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    database_url: SecretStr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("append", "publish"))
    parser.add_argument("--database-config", type=Path, required=True)
    parser.add_argument("--broker-config", type=Path, required=True)
    parser.add_argument("--fact", type=Path)
    parser.add_argument("--max-messages", type=int, default=100)
    parser.add_argument("--max-seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        broker = BrokerConfig.read_private(args.broker_config)
        db = DatabaseConfig.model_validate_json(private_bytes(args.database_config, limit=16384))
        if not db.database_url.get_secret_value().startswith("postgresql://"):
            raise ValueError
        outbox = ObservationOutbox(db.database_url.get_secret_value())
        producer, topology = build_producer(broker)
        stream, partitions = topology.inspect()
        if args.command == "append":
            if args.fact is None:
                raise ValueError
            fact = ObservationVersion.model_validate_json(private_bytes(args.fact, limit=8192))
            outbox.bind(stream, partitions)
            status = outbox.append(stream, partitions, fact)
            sys.stdout.write('{"status":"' + status + '"}\n')
        else:
            if args.fact is not None:
                raise ValueError
            stop = threading.Event()
            for signum in (signal.SIGTERM, signal.SIGINT):
                signal.signal(signum, lambda _signum, _frame: stop.set())
            count = ObservationPublisher(outbox, producer, topology).run(
                max_messages=args.max_messages, max_seconds=args.max_seconds, stop_event=stop
            )
            sys.stdout.write('{"status":"completed","published":' + str(count) + "}\n")
        return 0
    except Exception:  # noqa: BLE001 - CLI deliberately returns a fixed error without private inputs
        sys.stderr.write('{"error":"source_observations_unavailable"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
