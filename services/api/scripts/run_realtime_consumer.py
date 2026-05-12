from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.realtime_consumer_runner import (  # noqa: E402
    build_signal_stop_event,
    run_realtime_consumer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the long-running RetailOps realtime event consumer.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Stop after processing this many Kafka messages. Intended for smoke tests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    handled_messages = run_realtime_consumer(
        stop_event=build_signal_stop_event(),
        max_messages=args.max_messages,
    )
    logging.getLogger(__name__).info(
        "Realtime consumer stopped after handling %s message(s)",
        handled_messages,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
