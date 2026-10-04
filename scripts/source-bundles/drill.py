# ruff: noqa: INP001
"""Generate an approved native fixture and require actual Source HTTP + typed AI import."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def command(args: list[str], *, cwd: Path, env: dict | None = None, timeout: int = 300) -> str:
    result = subprocess.run(  # noqa: S603 - fixed argument arrays, captured output; never shell
        args, cwd=cwd, env=env, timeout=timeout, capture_output=True, text=True, check=False
    )
    if result.returncode:
        msg = "owned_command_failed"
        raise RuntimeError(msg)
    return result.stdout


def private_file(path: Path, value: dict) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def http_status(url: str, token: str | None = None) -> int:
    request = urllib.request.Request(  # noqa: S310 - only the exclusively owned loopback socket
        url, headers={"Authorization": "Bearer " + token} if token else {}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def run(args: argparse.Namespace, report: dict) -> None:  # noqa: PLR0912, PLR0915 - ordered acceptance/cleanup
    pin = json.loads((ROOT / "scripts/source-bundles/owner.json").read_bytes())
    producer, client = args.producer_root.resolve(), args.client_root.resolve()
    for root, commit in ((producer, pin["producer_commit"]), (client, pin["client_commit"])):
        if command(["git", "rev-parse", "HEAD"], cwd=root).strip() != commit:
            msg = "immutable_checkout_mismatch"
            raise ValueError(msg)
        command(["git", "diff", "--exit-code", "HEAD"], cwd=root)
    for relative, expected in pin["producer_files"].items():
        if digest(producer / relative) != expected:
            msg = "producer_dependency_pin_mismatch"
            raise ValueError(msg)
    for relative, expected in pin["client_files"].items():
        if digest(client / relative) != expected:
            msg = "client_copy_pin_mismatch"
            raise ValueError(msg)
    if (ROOT / "services/api/app/services/source_bundle_wire.py").read_bytes() != (
        client / "src/retailops_ai/source_bundle/wire.py"
    ).read_bytes():
        msg = "wire_contract_mismatch"
        raise ValueError(msg)
    report["pins"] = pin
    generated = producer / "data/generated" / ("ai10-bundle-" + uuid4().hex)
    generated.mkdir(mode=0o700, parents=True, exist_ok=False)
    process = None
    listener = None
    private = None
    stage = "generate_native_source"
    try:
        with tempfile.TemporaryDirectory(prefix="retailops-ai10-bundle-gate-") as directory:
            private = Path(directory).resolve()
            source_receipt = private / "source.json"
            command(
                [
                    args.producer_python,
                    "-m",
                    "data.anomalies.run_source",
                    "--profile",
                    "ai-smoke",
                    "--example",
                    "--output-root",
                    str(generated / "source"),
                    "--output",
                    str(source_receipt),
                ],
                cwd=producer,
            )
            source = json.loads(source_receipt.read_bytes())
            if source["status"] != "passed" or source["source_schema_version"] != "2.8.0":
                msg = "native_source_generation_failed"
                raise ValueError(msg)
            if source["model_ready"] or source["anomaly_ready"] or source["source_ready"]:
                msg = "unexpected_model_qualification_claim"
                raise ValueError(msg)
            source_path = Path(source["directory"])
            if not source_path.is_absolute():
                source_path = producer / source_path
            stage = "qualify_source_lifecycle"
            qualification_receipt = private / "qualification.json"
            command(
                [
                    args.producer_python,
                    "-m",
                    "data.inventory.run_qualification",
                    "--source",
                    str(source_path),
                    "--output-root",
                    str(generated / "qualification"),
                    "--output",
                    str(qualification_receipt),
                ],
                cwd=producer,
            )
            qualification = json.loads(qualification_receipt.read_bytes())
            qpath = Path(qualification["directory"])
            if not qpath.is_absolute():
                qpath = producer / qpath
            stage = "export_existing_immutable_facts"
            export = json.loads(
                command(
                    [
                        args.producer_python,
                        "-c",
                        (
                            "import json,sys; from pathlib import Path; from data.export.inventory_snapshot import export_inventory_snapshot; "
                            "r=export_inventory_snapshot(Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4]),required_use_cases=('anomaly_source',)); "
                            "print(json.dumps({'publication':r['publication'],'path':r['path']}))"
                        ),
                        str(source_path),
                        source["dataset_id"],
                        str(qpath),
                        str(generated / "snapshots"),
                    ],
                    cwd=producer,
                )
            )
            snapshot = Path(export["path"])
            stage = "seal_bundle"
            store = private / "store"
            api_env = dict(os.environ, PYTHONPATH=str(ROOT / "services/api"))
            bundle = json.loads(
                command(
                    [
                        args.api_python,
                        "-m",
                        "scripts.publish_source_bundle",
                        "--snapshot-dir",
                        str(snapshot),
                        "--store",
                        str(store),
                    ],
                    cwd=ROOT / "services/api",
                    env=api_env,
                )
            )
            token = secrets.token_hex(32)
            policy_path = private / "policy.json"
            missing = "source-bundle-sha256-" + "0" * 64
            denied = "source-bundle-sha256-" + "1" * 64
            policy: dict = {
                "version": "retailops-source-bundle-access-1.0",
                "principals": [
                    {
                        "principal_id": "native-fixture",
                        "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "bundle_ids": [bundle["bundle_id"], missing],
                    }
                ],
            }
            private_file(policy_path, policy)
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
            stage = "start_owned_source_api"
            api_env.update(
                RETAILOPS_SOURCE_BUNDLE_ROOT=str(store),
                RETAILOPS_SOURCE_BUNDLE_ACCESS_POLICY=str(policy_path),
            )
            with (private / "api-private.log").open("wb") as log:
                process = subprocess.Popen(  # noqa: S603 - own interpreter/socket; no credentials in arguments
                    [
                        args.api_python,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--fd",
                        str(listener.fileno()),
                        "--log-level",
                        "warning",
                        "--no-access-log",
                    ],
                    cwd=ROOT / "services/api",
                    env=api_env,
                    pass_fds=(listener.fileno(),),
                    stdout=log,
                    stderr=log,
                )
            url = origin + "/integration/bundles/v1/" + bundle["bundle_id"]
            until = time.monotonic() + 30
            while True:
                try:
                    if http_status(url + "/manifest") == 401:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                if time.monotonic() > until or process.poll() is not None:
                    msg = "owned_api_startup_failed"
                    raise RuntimeError(msg)
                time.sleep(0.1)
            stage = "authenticated_typed_download_and_reuse"
            config = private / "client.json"
            private_file(
                config,
                {
                    "base_url": origin,
                    "credential": token,
                    "allow_http_loopback": True,
                    "bundle_id": bundle["bundle_id"],
                },
            )
            client_env = dict(os.environ, PYTHONPATH=str(client / "src"))
            imported = private / "data/generated"
            cli = [
                args.client_python,
                "-m",
                "retailops_ai.source_bundle.cli",
                "--config",
                str(config),
                "--generated-root",
                str(imported),
                "--require-use-case",
                "anomaly_source",
            ]
            imports = [json.loads(command(cli, cwd=client, env=client_env)) for _ in range(2)]
            if [r["status"] for r in imports] != ["published", "reused"]:
                msg = "immutable_import_reuse_failed"
                raise ValueError(msg)
            for value in imports:
                if (
                    value["tables"] != 43
                    or value["rows"] != 31623
                    or value["replay_handoff"] is not False
                    or value["bundle_id"] != bundle["bundle_id"]
                    or value["snapshot_id"] != bundle["snapshot_id"]
                    or value["source_dataset_id"] != bundle["source_dataset_id"]
                    or value["source_snapshot_version"] != "1.2.0"
                ):
                    msg = "native_import_identity_or_inventory_mismatch"
                    raise ValueError(msg)
            stage = "fail_closed_authorization_and_integrity"
            checks = {
                "anonymous": http_status(url + "/manifest"),
                "wrong_credential": http_status(url + "/manifest", secrets.token_hex(32)),
                "foreign_bundle": http_status(
                    origin + "/integration/bundles/v1/" + denied + "/manifest", token
                ),
                "missing_granted_bundle": http_status(
                    origin + "/integration/bundles/v1/" + missing + "/manifest", token
                ),
                "cross_scope_bounded_rest": http_status(
                    origin + "/integration/v2/capabilities", token
                ),
            }
            if checks != {
                "anonymous": 401,
                "wrong_credential": 401,
                "foreign_bundle": 403,
                "missing_granted_bundle": 404,
                "cross_scope_bounded_rest": 401,
            }:
                msg = "authorization_boundary_failed"
                raise ValueError(msg)
            reference = next(f for f in bundle["files"] if f["path"].endswith(".parquet"))
            target = store / bundle["bundle_id"] / reference["path"]
            original = target.read_bytes()
            target.write_bytes(b"corrupt")
            try:
                checks["corrupt_file"] = http_status(url + "/files/" + reference["file_id"], token)
                rejected = imported.parent / "rejected/generated"
                failed = subprocess.run(  # noqa: S603 - same fixed private CLI/config, expected rejection
                    [
                        *cli[:5],
                        "--generated-root",
                        str(rejected),
                        "--require-use-case",
                        "anomaly_source",
                    ],
                    cwd=client,
                    env=client_env,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if (
                    checks["corrupt_file"] != 503
                    or failed.returncode != 1
                    or rejected.exists()
                    or token in failed.stdout + failed.stderr
                ):
                    msg = "corrupt_bytes_not_rejected"
                    raise ValueError(msg)
                checks["corrupt_import_rejected_without_output"] = True
            finally:
                target.write_bytes(original)
            policy["principals"][0]["credential_sha256"] = hashlib.sha256(
                secrets.token_bytes(32)
            ).hexdigest()
            policy_path.write_text(json.dumps(policy))
            checks["revoked_on_next_request"] = http_status(url + "/manifest", token)
            if checks["revoked_on_next_request"] != 401:
                msg = "credential_revocation_failed"
                raise ValueError(msg)
            report.update(
                status="passed",
                source_dataset_id=bundle["source_dataset_id"],
                snapshot_id=bundle["snapshot_id"],
                bundle_id=bundle["bundle_id"],
                source_snapshot_version="1.2.0",
                source_schema_version="2.8.0",
                tables=43,
                rows=31623,
                files=len(bundle["files"]),
                bytes=bundle["total_bytes"],
                imports=[{k: v for k, v in r.items() if k != "directory"} for r in imports],
                authorization_and_integrity=checks,
                model_ready=False,
                evaluation_truth_included=False,
                replay_handoff=False,
                transport="actual_owned_loopback_http_source_api",
                consumer="actual_typed_native_importer",
                source_commit=command(["git", "rev-parse", "HEAD"], cwd=ROOT).strip(),
            )
    except Exception:
        report.update(status="failed", failed_stage=stage)
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if listener is not None:
            listener.close()
        shutil.rmtree(generated)
        report["cleanup"] = {
            "owned_api_stopped": process is None or process.poll() is not None,
            "owned_source_fixture_removed": not generated.exists(),
            "private_credentials_removed": private is None or not private.exists(),
        }
        for root in (producer, client):
            command(["git", "diff", "--exit-code", "HEAD"], cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-root", type=Path, required=True)
    parser.add_argument("--client-root", type=Path, required=True)
    parser.add_argument("--producer-python", required=True)
    parser.add_argument("--api-python", required=True)
    parser.add_argument("--client-python", required=True)
    args = parser.parse_args()
    report = {
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(),
        "scope": "native fixture protocol acceptance; no model qualification",
    }
    with suppress(Exception):
        run(args, report)
    report["finished_at"] = datetime.now(UTC).isoformat()
    path = ROOT / "ci-cd/reports/source-bundles/report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(path.relative_to(ROOT))}))  # noqa: T201 - safe CLI receipt
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
