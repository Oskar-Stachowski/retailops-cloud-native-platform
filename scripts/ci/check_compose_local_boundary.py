"""Reject published local Compose ports outside loopback, including at runtime."""

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOPBACK = "127.0.0.1"
BASE_PORTS = {
    "frontend": 1,
    "api": 1,
    "db": 1,
    "redpanda": 2,
    "prometheus": 1,
    "grafana": 1,
}


def run(compose, *args):
    # Test an attempted public override as well as the normal local setup.
    env = {**os.environ, "HOST_BIND": "0.0.0.0"}
    return subprocess.check_output(
        [*compose, *args], cwd=ROOT, env=env, text=True
    )


def check_ports(services, expected, label):
    if "seed" in services:
        raise AssertionError(f"{label}: seed must remain an explicit operation")
    for service, count in expected.items():
        actual = len(services.get(service, {}).get("ports", []))
        if actual != count:
            raise AssertionError(f"{label}: {service} has {actual} published ports, expected {count}")
    for service, definition in services.items():
        for port in definition.get("ports", []):
            if port.get("host_ip") != LOOPBACK:
                raise AssertionError(f"{label}: {service} publishes {port} outside {LOOPBACK}")


def config(compose, profiles, expected, label):
    args = [item for profile in profiles for item in ("--profile", profile)]
    rendered = json.loads(run(compose, *args, "config", "--format", "json"))
    check_ports(rendered["services"], expected, label)
    print(f"{label}: all published ports bind to {LOOPBACK}; seed is excluded")


def check_runtime(compose):
    raw = run(compose, "ps", "--format", "json").strip()
    try:
        parsed = json.loads(raw)
        containers = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        containers = [json.loads(line) for line in raw.splitlines()]
    by_service = {container["Service"]: container for container in containers}
    for service, count in BASE_PORTS.items():
        container = by_service.get(service)
        if container is None or container.get("State") != "running":
            raise AssertionError(f"runtime: {service} is not running")
        publishers = [
            item for item in (container.get("Publishers") or [])
            if item.get("PublishedPort")
        ]
        if len(publishers) != count:
            raise AssertionError(f"runtime: {service} has {len(publishers)} published ports, expected {count}")
        for publisher in publishers:
            if publisher.get("URL", publisher.get("HostIp")) != LOOPBACK:
                raise AssertionError(f"runtime: {service} publishes {publisher} outside {LOOPBACK}")
    print(f"runtime: all {sum(BASE_PORTS.values())} published ports bind to {LOOPBACK}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    compose = shlex.split(os.environ.get("COMPOSE", "docker compose"))
    config(compose, ("dev", "observability", "test"), BASE_PORTS, "local Compose")
    overlay = [*compose]
    if not any(arg in ("-f", "--file") for arg in compose):
        overlay += ["-f", "docker-compose.yml"]
    overlay += ["-f", "docker-compose.observability.yml"]
    config(overlay, ("observability",), {k: v for k, v in BASE_PORTS.items() if k != "frontend"}, "observability overlay")
    if args.runtime:
        check_runtime(compose)


if __name__ == "__main__":
    main()
