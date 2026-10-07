"""Typed contract, private input and fail-stop checks for the operational producer."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from app.services.source_observation_broker import BrokerConfig
from app.services.source_observation_outbox import (
    ObservationError,
    ObservationPublisher,
    event_for,
    private_bytes,
)
from app.services.source_observation_wire import (
    Envelope,
    ObservationVersion,
    Stream,
    canonical,
)

CONTRACT = Path(__file__).resolve().parents[1] / "app/contracts/source-observations-v1"


def fact(*, version=1, units=10, observation_id=None):
    return ObservationVersion(
        id=str(uuid4()),
        observation_id=observation_id or str(uuid4()),
        business_date=date(2026, 10, 1),
        product_id=str(uuid4()),
        selling_location_id=str(uuid4()),
        channel="store",
        version=version,
        observed_units=units,
        observation_status="observed_positive",
        available_at=datetime(2026, 10, 2, tzinfo=UTC),
        history_policy_version="observed-quantity-history-1.0.0",
    )


def stream():
    return Stream(
        source_authority_id=str(uuid4()),
        cluster_id="native-cluster",
        topic_id="native-topic",
    )


def test_schema_byte_pin_and_generated_types_match_upstream():
    pin = json.loads((CONTRACT / "upstream.json").read_bytes())
    raw = (CONTRACT / "event.schema.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
    generated = Envelope.model_json_schema()
    expected = json.loads(raw)
    expected.pop("$schema")
    assert generated == expected
    Draft202012Validator(expected, format_checker=FormatChecker()).validate(
        json.loads(canonical(event_for(stream(), fact())))
    )


def test_event_identity_is_stable_per_fact_and_authority():
    owner, row = stream(), fact()
    assert event_for(owner, row) == event_for(owner, row)
    assert event_for(owner, row).event_id != event_for(stream(), row).event_id
    assert (
        event_for(owner, row).event_id
        != event_for(owner, row.model_copy(update={"observed_units": 4})).event_id
    )


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"version": 0},
        {"version": 2**63},
        {"observed_units": True},
        {"observed_units": -1},
        {"observed_units": 0},
        {"observed_units": None},
        {"observation_status": "missing"},
        {"observation_status": "closed"},
        {"available_at": "2026-10-02T00:00:00+02:00"},
        {"available_at": "2026-10-02T00:00:00"},
        {"id": "foreign"},
        {"channel": "unknown"},
        {"history_policy_version": "unsupported"},
        {"extra": 1},
    ],
)
def test_invalid_private_native_versions_rejected(change):
    document = json.loads(canonical(fact()))
    document.update(change)
    with pytest.raises(ValidationError):
        ObservationVersion.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    "status,units",
    [("missing", None), ("closed", 0), ("observed_zero", 0), ("observed_positive", 1)],
)
def test_zero_closed_missing_are_distinct(status, units):
    document = json.loads(canonical(fact()))
    document.update(observation_status=status, observed_units=units)
    row = ObservationVersion.model_validate_json(json.dumps(document))
    assert row.observation_status == status and row.observed_units == units


@pytest.mark.parametrize(
    "kind",
    ["permissions", "symlink", "duplicate", "nonfinite", "oversized", "directory"],
)
def test_private_input_rejects_unsafe_or_ambiguous_files(tmp_path, kind):
    path = tmp_path / "private.json"
    path.write_bytes(b'{"private":"not-in-error"}')
    path.chmod(0o600)
    if kind == "permissions":
        path.chmod(0o644)
    elif kind == "symlink":
        target = tmp_path / "link"
        target.symlink_to(path)
        path = target
    elif kind == "duplicate":
        path.write_bytes(b'{"a":1,"a":2}')
    elif kind == "nonfinite":
        path.write_bytes(b'{"a":NaN}')
    elif kind == "oversized":
        path.write_bytes(b" " * 1025)
    else:
        path = tmp_path
    with pytest.raises(ObservationError, match="^observation_private_input_invalid$"):
        private_bytes(path, limit=1024)


@pytest.mark.parametrize(
    "change",
    [
        {"security_protocol": "PLAINTEXT"},
        {"sasl_mechanism": "PLAIN"},
        {"ca_file": "relative"},
        {"password": ""},
        {"username": ""},
        {"bootstrap_servers": "https://host:9092"},
        {"bootstrap_servers": "user:secret@host:9092"},
        {"bootstrap_servers": "host:9092/path"},
        {"bootstrap_servers": "host:9092?query"},
        {"bootstrap_servers": "host:9092 "},
        {"bootstrap_servers": "host"},
        {"bootstrap_servers": ",".join(["host:9092"] * 9)},
        {"arbitrary_native_option": True},
    ],
)
def test_broker_config_has_no_plaintext_or_arbitrary_options(change):
    config = {
        "source_authority_id": str(uuid4()),
        "bootstrap_servers": "host:9092",
        "username": "private-user",
        "password": "private-secret",
        "ca_file": "/private/ca.crt",
    }
    config.update(change)
    with pytest.raises(ValidationError):
        BrokerConfig.model_validate_json(json.dumps(config))


def test_valid_private_config_and_backend_verify_tls(tmp_path):
    config = {
        "source_authority_id": str(uuid4()),
        "bootstrap_servers": "host:9092",
        "username": "private-user",
        "password": "private-secret",
        "ca_file": "/private/ca.crt",
    }
    path = tmp_path / "config"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    parsed = BrokerConfig.read_private(path)
    assert "private-user" not in repr(parsed) and "private-secret" not in repr(parsed)
    assert parsed.backend()["enable.ssl.certificate.verification"] is True
    assert parsed.backend()["ssl.endpoint.identification.algorithm"] == "https"
    assert parsed.backend()["allow.auto.create.topics"] is False


def test_first_failure_stops_following_work():
    topology = SimpleNamespace(
        inspect=lambda: (_ for _ in ()).throw(ValueError("private-metadata"))
    )
    publisher = ObservationPublisher(None, None, topology)
    with pytest.raises(ObservationError, match="^observation_publication_unavailable$"):
        publisher.once()
    assert publisher.failed
    with pytest.raises(ObservationError, match="^observation_publisher_stopped$"):
        publisher.once()


@pytest.mark.parametrize(
    "messages,seconds", [(True, 1), (0, 1), (20001, 1), (1, True), (1, 0), (1, 3601)]
)
def test_run_bounds_do_not_touch_sql_or_broker(messages, seconds):
    with pytest.raises(
        ObservationError, match="^observation_publisher_bounds_invalid$"
    ):
        ObservationPublisher(None, None, None).run(
            max_messages=messages, max_seconds=seconds
        )


def private_broker_document(config):
    document = json.loads(config.model_dump_json())
    document.update(
        username=config.username.get_secret_value(),
        password=config.password.get_secret_value(),
    )
    return document


def test_private_child_configuration_preserves_authentication_values():
    config = BrokerConfig.model_validate_json(
        json.dumps(
            {
                "source_authority_id": str(uuid4()),
                "bootstrap_servers": "host:9092",
                "username": "explicit-fixture-user",
                "password": "explicit-fixture-password",
                "ca_file": "/private/ca.crt",
            }
        )
    )
    clone = BrokerConfig.model_validate_json(
        json.dumps(private_broker_document(config))
    )
    assert clone.username.get_secret_value() == config.username.get_secret_value()
    assert clone.password.get_secret_value() == config.password.get_secret_value()
    assert "explicit-fixture-user" not in repr(clone)
    assert "explicit-fixture-password" not in repr(clone)
