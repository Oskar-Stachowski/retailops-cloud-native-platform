"""Inspect retained messages and explicitly replay a reviewed correction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.repositories.realtime_quarantine_repository import RealtimeQuarantineRepository
from app.services.realtime_quarantine import replay_quarantined_message


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    listing = subparsers.add_parser("list")
    listing.add_argument("--limit", type=int, default=100)
    show = subparsers.add_parser("show")
    show.add_argument("--id", required=True)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--id", required=True)
    replay.add_argument("--event-file", type=Path, required=True)
    replay.add_argument("--operator", required=True)
    arguments = parser.parse_args()
    repository = RealtimeQuarantineRepository()
    if arguments.command == "list":
        result = repository.pending(limit=arguments.limit)
    elif arguments.command == "show":
        result = repository.get(arguments.id)
    else:
        result = replay_quarantined_message(
            arguments.id,
            event=json.loads(arguments.event_file.read_text(encoding="utf-8")),
            operator=arguments.operator,
            bootstrap_servers=get_settings().broker_bootstrap_servers or "",
            repository=repository,
        )
    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
