"""Reproduce AI-00 event/API observations offline, without a DB or Kafka client."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from collections import Counter
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.realtime_metrics_repository import RealtimeMetricsRepository
from app.services.realtime_consumer import (
    EVENT_TOPICS as CONSUMER_TOPICS,
)
from app.services.realtime_consumer import (
    RealtimeEventConsumer,
    RealtimeEventEnvelope,
    build_default_event_handlers,
)
from app.services.realtime_consumer_runner import (
    RealtimeConsumerRunnerConfig,
    RealtimeKafkaConsumerRunner,
)
from data.generator.main import DatasetGenerationConfig
from data.generator.realtime import (
    EVENT_TOPICS,
    RealtimeEventGenerationConfig,
    build_realtime_events,
)


def load_events(directory: Path, products: int | None) -> list[dict]:
    tables = {}
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as source:
            tables[path.stem] = list(csv.DictReader(source))
    return build_realtime_events(
        tables,
        RealtimeEventGenerationConfig(
            dataset=DatasetGenerationConfig(profile="small", seed=42, products=products),
            max_events=None,
        ),
    )


def runner_probe(
    raw: str, *, database_failure: bool = False, handler_failure: bool = False
) -> dict:
    """Invoke the real runner and consumer with recording, non-network collaborators."""
    repository = Mock(spec=RealtimeMetricsRepository)
    repository.is_event_processed.return_value = False
    if database_failure:
        repository.is_event_processed.side_effect = RuntimeError("audit: DB unavailable")
        repository.record_event_log.side_effect = RuntimeError("audit: quarantine unavailable")
        repository.upsert_consumer_state.side_effect = RuntimeError("audit: state unavailable")
    consumer = RealtimeEventConsumer(repository=repository)
    if handler_failure:
        consumer.register_handler(
            "sale_completed", Mock(side_effect=RuntimeError("audit: handler"))
        )
    kafka = Mock()
    message = Mock()
    message.value.return_value = raw
    message.topic.return_value = "retailops.sales.v1"
    message.partition.return_value = 0
    message.offset.return_value = 42
    runner = RealtimeKafkaConsumerRunner(
        kafka_consumer=kafka,
        event_consumer=consumer,
        config=RealtimeConsumerRunnerConfig(
            bootstrap_servers="unused.invalid:9092",
            group_id="offline-audit",
            client_id="offline-audit",
            topics=("retailops.sales.v1",),
        ),
    )
    runner._handle_message(message)
    return {
        "synchronous_commits": sum(
            c.kwargs.get("asynchronous") is False for c in kafka.commit.call_args_list
        ),
        "record_event_log_attempts": repository.record_event_log.call_count,
        "failed_events": consumer.state.failed_events,
        "dead_letter_counter": consumer.state.dead_lettered_events,
        "database_is_mock": True,
        "durability_verified": False,
    }


def measure(first: Path, contrast: Path) -> dict:
    repo = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (repo / "events/contracts/retailops-realtime-events.v1.contract.json").read_text()
    )
    events, other = load_events(first, None), load_events(contrast, 20)
    by_id = {e["event_id"]: e for e in events}
    assert len(by_id) == len(events)
    sale = next(e for e in events if e["event_type"] == "sale_completed")
    accepted = {}
    missing_topic = {k: v for k, v in sale.items() if k != "topic"}
    for name, value in {
        "missing_topic": missing_topic,
        "wrong_topic": {**sale, "topic": "retailops.wrong.v999"},
        "unsupported_version": {**sale, "schema_version": "999"},
        "empty_payload": {**sale, "payload": {}},
    }.items():
        try:
            RealtimeEventEnvelope.from_dict(value)
            accepted[name] = True
        except (ValueError, TypeError):
            accepted[name] = False
    registry_types = set(contract["supported_event_types"])
    registry_topics = set(contract["supported_topics"])
    emitted_topics = {e["topic"] for e in events}
    compose = (repo / "docker-compose.yml").read_text()
    init_loop = re.search(r"for topic in (.*?)\n\s*do\n", compose, re.DOTALL)
    assert init_loop is not None, "Inspect changed topic initialization before auditing it."
    compose_topics = set(re.findall(r"retailops\.[\w.]+", init_loop.group(1)))
    assert compose_topics
    envelope_count = sum(bool(RealtimeEventEnvelope.from_dict(e)) for e in events)
    changed = [
        e
        for e in other
        if e["event_id"] in by_id and e["payload"] != by_id[e["event_id"]]["payload"]
    ]
    runner = {
        "invalid_json": runner_probe("not-json"),
        "handler_failure": runner_probe(json.dumps(sale), handler_failure=True),
        "database_and_quarantine_failure": runner_probe(json.dumps(sale), database_failure=True),
    }
    repository = Mock(spec=RealtimeMetricsRepository)
    repository.is_event_processed.return_value = False
    consumer = RealtimeEventConsumer(repository=repository)
    forecast = next(e for e in events if e["event_type"] == "forecast_generated")
    outcome = consumer.process_event(forecast)
    schema = app.openapi()
    paths = (
        "/products",
        "/sales",
        "/inventory-snapshots",
        "/forecasts",
        "/forecast-runs",
        "/inventory-risks",
        "/notifications",
    )
    lists = {}
    client = TestClient(app)
    for path in paths:
        operation = schema["paths"][path]["get"]
        parameters = {p["name"]: p["schema"] for p in operation.get("parameters", [])}
        model = operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].split("/")[-1]
        properties = schema["components"]["schemas"][model]["properties"]
        item_ref = properties["items"]["items"]["$ref"].split("/")[-1]
        lists[path] = {
            "query_parameters": sorted(parameters),
            "limit": parameters["limit"],
            "offset": parameters["offset"],
            "response_model": model,
            "response_fields": sorted(properties),
            "item_fields": sorted(schema["components"]["schemas"][item_ref]["properties"]),
            "invalid_limit_status": client.get(path, params={"limit": 0}).status_code,
            "invalid_offset_status": client.get(path, params={"offset": -1}).status_code,
        }
    identity = client.get("/me?user_id=platform-admin")
    return {
        "events": {
            "count": len(events),
            "by_type": dict(sorted(Counter(e["event_type"] for e in events).items())),
            "generator_consumer_routing_equal": EVENT_TOPICS == CONSUMER_TOPICS,
            "consumer_accepted_envelopes": envelope_count,
            "types_missing_from_registry": sorted(set(EVENT_TOPICS) - registry_types),
            "emitted_topics_missing_from_registry": sorted(emitted_topics - registry_topics),
            "registry_topics_not_emitted": sorted(registry_topics - emitted_topics),
            "compose_topics": sorted(compose_topics),
            "emitted_topics_not_initialized": sorted(emitted_topics - compose_topics),
            "malformed_envelopes_accepted": accepted,
            "reused_ids_with_changed_payload_100_vs_20": len(changed),
            "changed_payload_types": dict(
                sorted(Counter(e["event_type"] for e in changed).items())
            ),
            "id_scope_note": (
                "Separate generated snapshots, not duplicates within one snapshot; "
                "IDs lack snapshot/version scope."
            ),
        },
        "ack_failure_probes": runner,
        "forecast_projection_probe": {
            "status": outcome["status"],
            "repository_methods_called": sorted({c[0] for c in repository.method_calls}),
            "default_handler_names": sorted(
                {h.__name__ for h in build_default_event_handlers().values()}
            ),
            "scope": "Real consumer, mock metric repository; no domain DB or broker.",
        },
        "openapi": {
            "sha256_canonical_json": hashlib.sha256(
                json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "version": schema["openapi"],
            "api_info": schema["info"],
            "paths": lists,
            "identity": {"http_status": identity.status_code, **identity.json()},
            "scope": (
                "OpenAPI generated from app plus validation-only HTTP requests in TestClient; "
                "no successful list DB queries."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--contrast", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Expected injected failures; their outcomes are recorded.
    report = measure(args.first, args.contrast)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Contract audit written to {args.output}")


if __name__ == "__main__":
    main()
