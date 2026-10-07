"""Read original model publications through the built RetailOps UI on owned ports."""

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request


def run_native_browser(
    *, api_url, control, policy_path, token, cases, frontend, report
):
    assert frontend.joinpath("dist/index.html").is_file(), (
        "Build the real frontend first"
    )
    control.mkdir(mode=0o700)
    for name, value in (
        ("credential", token),
        ("expected.json", json.dumps(cases)),
    ):
        path = control / name
        path.write_text(value)
        path.chmod(0o600)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {
        **os.environ,
        "AI10_NATIVE_API_URL": api_url,
        "AI10_NATIVE_BROWSER_CONTROL": str(control),
        "AI10_NATIVE_BROWSER_POLICY": str(policy_path),
        "AI10_NATIVE_BROWSER_REPORT": str(report),
        "FRONTEND_BASE_URL": f"http://127.0.0.1:{port}",
    }
    node = shutil.which("node")
    assert node, "The dedicated native UI gate requires Node"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with (control / "preview.log").open("wb") as log:
        preview = subprocess.Popen(
            [
                node,
                "node_modules/vite/bin/vite.js",
                "preview",
                "--config",
                "vite.native-preview.config.js",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=frontend,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                assert preview.poll() is None, "Owned native UI preview stopped"
                try:
                    with opener.open(env["FRONTEND_BASE_URL"], timeout=1) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, "Owned native UI not ready"
                    time.sleep(0.1)
            subprocess.run(
                [
                    node,
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "--project=native-intelligence-chromium",
                ],
                cwd=frontend,
                env=env,
                check=True,
                timeout=240,
            )
            result = json.loads(report.read_text())
            assert result["status"] == "passed"
            assert result["fixture_fallback"] is False
            assert result["rows"] == sum(len(case["items"]) for case in cases)
            return result
        finally:
            preview.terminate()
            try:
                preview.wait(timeout=10)
            except subprocess.TimeoutExpired:
                preview.kill()
                preview.wait(timeout=5)
