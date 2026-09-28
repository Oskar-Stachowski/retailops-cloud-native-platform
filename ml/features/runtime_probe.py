from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
from pathlib import Path


def probe(payload: dict) -> dict[str, bool]:
    try:
        importlib.util.find_spec("data.generator")
        generator_absent = False
    except ModuleNotFoundError:
        generator_absent = True
    try:
        Path("/worker/forbidden-write").write_text("probe", encoding="utf-8")
        readonly = False
    except OSError:
        readonly = True
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            network_absent = False
    except OSError:
        network_absent = True
    return {
        "supplied_source_path_absent": not Path(payload["source_path"]).exists(),
        "source_mount_absent": not Path("/source").exists(),
        "host_workspace_absent": not Path("/Users/oskarstachowski").exists(),
        "truth_files_absent": not any(Path("/worker").rglob("*truth*")),
        "generator_absent": generator_absent,
        "docker_socket_absent": not Path("/var/run/docker.sock").exists(),
        "worker_readonly": readonly,
        "network_absent": network_absent,
        "host_canary_absent": "RETAILOPS_TRUTH_CANARY" not in os.environ,
        "unprivileged": os.geteuid() == 65534,
    }


if __name__ == "__main__":
    print(json.dumps(probe(json.load(sys.stdin)), sort_keys=True))  # noqa: T201 - probe output
