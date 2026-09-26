"""Validate real samples, Grafana queries and the unchanged two-minute outage alert."""

import base64
import json
import os
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PROM = os.environ.get("PROMETHEUS_BASE_URL", "http://localhost:9090")
GRAFANA = os.environ.get("GRAFANA_BASE_URL", "http://localhost:3001")
ALERT = "RetailOpsApiMetricsTargetDown"


def get(url, auth=False):
    headers = {}
    if auth:
        pair = (
            os.environ.get("GRAFANA_ADMIN_USER", "admin")
            + ":"
            + os.environ.get("GRAFANA_ADMIN_PASSWORD", "retailops")
        )
        headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
    with urlopen(Request(url, headers=headers), timeout=10) as response:
        return json.load(response)


def query(expression, grafana=False):
    base = GRAFANA + "/api/datasources/proxy/uid/retailops-prometheus" if grafana else PROM
    result = get(base + "/api/v1/query?" + urlencode({"query": expression}), auth=grafana)
    if result["status"] != "success":
        raise RuntimeError("Prometheus query failed")
    return result["data"]["result"]


def wait_for(description, predicate, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            print(description, flush=True)
            return value
        time.sleep(3)
    raise RuntimeError("Timed out: " + description)


def rule():
    matches = [
        r
        for group in get(PROM + "/api/v1/rules")["data"]["groups"]
        for r in group["rules"]
        if r["name"] == ALERT
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one API outage rule")
    return matches[0]


def rule_in_state(state):
    current = rule()
    # Loaded rules have unknown health until their first scheduled evaluation.
    return current if current["health"] == "ok" and current["state"] == state else None


def main():
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    compose = shlex.split(os.environ.get("COMPOSE", ""))
    if (
        not project.startswith("retailops-ci-")
        or "-p" not in compose
        or compose[compose.index("-p") + 1] != project
    ):
        raise RuntimeError("Fault injection requires the explicit disposable Compose project")
    report = {
        "status": "failed",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "local scrape availability; no production SLO or notification delivery claim",
    }
    path = ROOT / "ci-cd/reports/observability/incident-drill.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    def command(*args):
        subprocess.run(compose + list(args), cwd=ROOT, check=True, timeout=120)

    try:
        for job in ("retailops-api", "prometheus"):
            wait_for(job + " is scraped", lambda: query('up{job="' + job + '"} == 1'))
        for metric in (
            "retailops_api_info",
            "retailops_db_operations_total",
            "retailops_stream_metrics_generated_at_seconds",
        ):
            report[metric] = wait_for(metric + " has ingested samples", lambda: query(metric))
        report["grafana_query"] = wait_for(
            "Grafana datasource returns live API sample",
            lambda: query('up{job="retailops-api"} == 1', grafana=True),
        )
        dashboards = get(GRAFANA + "/api/search?query=RetailOps", auth=True)
        expected = {
            "retailops-overview",
            "retailops-api",
            "retailops-business-operations",
            "retailops-stream-processing",
        }
        if not expected.issubset({item["uid"] for item in dashboards}):
            raise RuntimeError("Required Grafana dashboards missing")
        report["dashboard_uids"] = sorted(expected)
        report["baseline_rule"] = wait_for(
            "Outage alert is initially inactive",
            lambda: rule_in_state("inactive"),
        )
        report["baseline_sli"] = wait_for(
            "Baseline scrape SLI recorded",
            lambda: query("retailops:api_scrape_availability:ratio5m"),
        )
        if float(report["baseline_sli"][0]["value"][1]) != 1:
            raise RuntimeError("Baseline scrape availability must be 1")
        started = time.monotonic()
        command("stop", "api")
        report["pending_rule"] = wait_for(
            "Outage alert entered pending", lambda: rule_in_state("pending")
        )
        report["firing_rule"] = wait_for(
            "Outage alert is firing",
            lambda: rule_in_state("firing"),
            seconds=210,
        )
        report["seconds_to_firing"] = round(time.monotonic() - started, 2)
        if report["firing_rule"]["duration"] != 120:
            raise RuntimeError("Outage alert must retain its real two-minute hold")
        report["outage_sli"] = query("retailops:api_scrape_availability:ratio5m")
        if not report["outage_sli"] or not 0 <= float(report["outage_sli"][0]["value"][1]) < 1:
            raise RuntimeError("Scrape SLI did not reflect outage")
        command("up", "-d", "--no-deps", "--no-recreate", "api")
        wait_for("API scrape recovered", lambda: query('up{job="retailops-api"} == 1'))
        report["recovered_rule"] = wait_for(
            "Outage alert resolved", lambda: rule_in_state("inactive")
        )
        report["recovered_grafana_query"] = query('up{job="retailops-api"} == 1', grafana=True)
        if not report["recovered_grafana_query"]:
            raise RuntimeError("Grafana did not see recovery")
        report["status"] = "passed"
    finally:
        # Always restore the stopped service; project cleanup belongs to the outer runner.
        command("up", "-d", "--no-deps", "--no-recreate", "api")
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
