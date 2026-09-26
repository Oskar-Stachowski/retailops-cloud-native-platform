# ruff: noqa: INP001, S603
"""Create, exercise and remove one isolated kind cluster; never use the user's context."""

import argparse
import copy
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
from drill import Drill
from release import compatible, require

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS = "cb0c79848247612bf71fb9ccf63a8ff3847b5ca1"
NODE = (
    "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
)
WORKLOADS = ("retailops-api", "retailops-frontend", "retailops-realtime-consumer")


def images_for(objects: list, release: dict) -> list:
    result = copy.deepcopy(objects)
    for obj in result:
        spec = obj.get("spec", {}).get("template", {}).get("spec", {})
        for container in spec.get("containers", []) + spec.get("initContainers", []):
            for component in ("api", "frontend"):
                if container["image"].split(":")[0] == "retailops-" + component:
                    container["image"] = release["images"][component]["tag"]
                    container["imagePullPolicy"] = "Never"
    return result


class KubernetesDrill(Drill):
    def __init__(self, report_dir: Path, log: object, temp: Path) -> None:
        super().__init__(report_dir, log)
        self.temp = temp
        self.config = temp / "kubeconfig"
        self.env["KUBECONFIG"] = str(self.config)
        self.env["KIND_EXPERIMENTAL_PROVIDER"] = "docker"
        self.kubectl = [
            "kubectl",
            "--kubeconfig",
            str(self.config),
            "--context",
            "kind-" + self.project,
        ]
        self.created = False
        self.forward = None
        self.report.update(
            image_mode="native source builds; not the published AMD64 registry artifacts",
            snapshot_excludes=["realtime_consumer_state (restart timestamps/counters)"],
            node_image=NODE,
        )

    def k(self, *args: str, data: dict | None = None, allow_failure: bool = False) -> str:
        return self.run([*self.kubectl, *args], data=data, allow_failure=allow_failure)

    def get(self, resource: str, namespace: str = "retailops") -> dict:
        return json.loads(self.k("-n", namespace, "get", resource, "-o", "json"))

    def apply(self, objects: list) -> None:
        self.k("apply", "-f", "-", data={"apiVersion": "v1", "kind": "List", "items": objects})

    def wait(self, name: str, namespace: str = "retailops") -> None:
        self.k("-n", namespace, "rollout", "status", "deployment/" + name, "--timeout=240s")

    def check(self, mode: str, *args: str, data: dict | None = None) -> dict:
        return json.loads(
            self.k(
                "-n",
                "retailops",
                "exec",
                "-i",
                "retailops-checker",
                "--",
                "python",
                "/kube/checks.py",
                mode,
                *args,
                data=data,
            )
        )

    def create(self) -> None:
        require(
            self.project not in self.run(["kind", "get", "clusters"]).split(),
            "Refuse to reuse an existing cluster",
        )
        config = self.temp / "kind.json"
        config.write_text(
            json.dumps(
                {
                    "kind": "Cluster",
                    "apiVersion": "kind.x-k8s.io/v1alpha4",
                    "networking": {"disableDefaultCNI": True, "podSubnet": "10.244.0.0/16"},
                    "nodes": [{"role": "control-plane"}],
                }
            )
        )
        self.created = True
        self.progress("Create isolated kind cluster with network-policy enforcement")
        self.run(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                self.project,
                "--kubeconfig",
                str(self.config),
                "--config",
                str(config),
                "--image",
                NODE,
            ],
            stream=True,
        )
        self.k("apply", "-f", str(ROOT / "scripts/kubernetes/vendor/kindnet.yaml"))
        self.k("-n", "kube-system", "rollout", "status", "daemonset/kindnet", "--timeout=240s")
        self.k("wait", "--for=condition=Ready", "nodes", "--all", "--timeout=240s")
        self.k("apply", "-f", str(ROOT / "k8s/base/namespaces/retailops.yaml"))
        self.k("apply", "-f", str(ROOT / "scripts/kubernetes/traefik.yaml"))
        self.wait("traefik", "traefik")
        node = self.get("nodes", "default")["items"][0]
        self.report["kubernetes"] = node["status"]["nodeInfo"]

    def preload_data_images(self) -> None:
        # Pull once into the host cache; later runs need no repeated registry downloads
        # inside fresh nodes. These shared cache tags are deliberately not deleted.
        refs = (
            "postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea",
            "redpandadata/redpanda:v25.3.6@sha256:ac152ec27adccf9482af2649d293f398eb03c860d7469fc49f86e30d870ea408",
        )
        for ref in refs:
            self.run(["docker", "pull", ref], stream=True)
            self.run(["kind", "load", "docker-image", "--name", self.project, ref], stream=True)
        self.report["data_images"] = list(refs)

    def render(self) -> list:
        directory = self.temp / "k8s"
        shutil.copytree(
            ROOT / "k8s", directory, ignore=shutil.ignore_patterns("runtime-secrets.env")
        )
        password = secrets.token_hex(24)
        secret = directory / "overlays/dev/secrets/runtime-secrets.env"
        secret.write_text(
            f"POSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql://retailops:{password}@postgres:5432/retailops\n"
        )
        secret.chmod(0o600)
        rendered = self.run(["kubectl", "kustomize", str(directory / "overlays/dev")])
        # Ruby is already required by k8s-smoke; no host Python YAML dependency.
        parsed = subprocess.run(
            [
                shutil.which("ruby"),
                "-ryaml",
                "-rjson",
                "-e",
                "puts JSON.generate(YAML.load_stream(STDIN.read).compact)",
            ],
            input=rendered,
            capture_output=True,
            text=True,
            check=True,
        )
        objects = json.loads(parsed.stdout)
        for obj in objects:
            if obj["kind"] == "Ingress":
                loopback = copy.deepcopy(obj["spec"]["rules"][0])
                loopback.pop(
                    "host"
                )  # Isolated loopback browser route; IP hosts are invalid in Ingress.
                obj["spec"]["rules"].append(loopback)
        return objects

    def load_images(self, release: dict) -> None:
        for component, item in release["images"].items():
            require(
                item["platform"] == "linux/" + self.report["kubernetes"]["architecture"],
                "Application image and node architecture differ",
            )
            self.run(
                ["kind", "load", "docker-image", "--name", self.project, item["tag"]], stream=True
            )
            info = json.loads(
                self.run(
                    [
                        "docker",
                        "exec",
                        self.project + "-control-plane",
                        "crictl",
                        "inspecti",
                        item["tag"],
                    ]
                )
            )
            item["cri_image_id"] = info["status"]["id"]
            labels = info["info"]["imageSpec"]["config"]["Labels"]
            require(
                labels["org.opencontainers.image.revision"] == release["source_commit"]
                and labels["org.opencontainers.image.version"] == release["version"]
                and labels["io.retailops.component"] == component,
                "Loaded image source/version/component mismatch",
            )

    def checker(self, release: dict) -> None:
        for name, file in (
            ("recovery", "scripts/db/recovery-checks.py"),
            ("release", "scripts/release/checks.py"),
            ("kube", "scripts/kubernetes/checks.py"),
        ):
            self.apply(
                [
                    {
                        "apiVersion": "v1",
                        "kind": "ConfigMap",
                        "metadata": {"name": "drill-" + name, "namespace": "retailops"},
                        "data": {"checks.py": (ROOT / file).read_text()},
                    }
                ]
            )
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "retailops-checker",
                "namespace": "retailops",
                "labels": {"app.kubernetes.io/part-of": "retailops-platform"},
            },
            "spec": {
                "automountServiceAccountToken": False,
                "restartPolicy": "Never",
                "securityContext": {
                    "runAsUser": 1000,
                    "runAsGroup": 1000,
                    "runAsNonRoot": True,
                    "seccompProfile": {"type": "RuntimeDefault"},
                },
                "containers": [
                    {
                        "name": "checks",
                        "image": release["images"]["api"]["tag"],
                        "imagePullPolicy": "Never",
                        "command": ["python", "-c", "import time; time.sleep(7200)"],
                        "env": [{"name": "RETAILOPS_K8S_DRILL", "value": "1"}],
                        "envFrom": [{"secretRef": {"name": "retailops-runtime-secrets"}}],
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "resources": {
                            "requests": {"cpu": "25m", "memory": "64Mi"},
                            "limits": {"cpu": "500m", "memory": "256Mi"},
                        },
                        "volumeMounts": [
                            {"name": n, "mountPath": "/" + n, "readOnly": True}
                            for n in ("recovery", "release", "kube")
                        ],
                    }
                ],
                "volumes": [
                    {"name": n, "configMap": {"name": "drill-" + n}}
                    for n in ("recovery", "release", "kube")
                ],
            },
        }
        self.apply([pod])
        self.k(
            "-n",
            "retailops",
            "wait",
            "pod/retailops-checker",
            "--for=condition=Ready",
            "--timeout=120s",
        )

    def start_forward(self) -> None:
        output = (self.report_dir / "port-forward.log").open("w")
        self.forward = subprocess.Popen(
            [
                *self.kubectl,
                "-n",
                "traefik",
                "port-forward",
                "deployment/traefik",
                "--address=127.0.0.1",
                "0:8000",
            ],
            cwd=ROOT,
            env=self.env,
            stdout=output,
            stderr=output,
        )
        output.close()
        for _ in range(60):
            match = re.search(
                r"Forwarding from 127\.0\.0\.1:(\d+)",
                (self.report_dir / "port-forward.log").read_text(),
            )
            if match:
                self.url = "http://127.0.0.1:" + match[1]
                return
            require(self.forward.poll() is None, "Ingress port-forward exited")
            time.sleep(0.5)
        require(condition=False, message="Ingress port-forward timed out")

    def http(self, path: str) -> int:
        try:
            with urlopen(  # noqa: S310 -- generated loopback HTTP origin
                Request(self.url + path, headers={"Host": "retailops.local"}),  # noqa: S310
                timeout=5,
            ) as response:
                return response.status
        except HTTPError as error:
            return error.code
        except URLError:
            return 0

    def until(self, check: object, message: str, timeout: int = 90) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(2)
        require(condition=False, message=message)

    def identities(self, release: dict) -> dict:
        result = {}
        for name in WORKLOADS:
            pods = json.loads(
                self.k(
                    "-n",
                    "retailops",
                    "get",
                    "pods",
                    "-l",
                    "app.kubernetes.io/name=" + name,
                    "-o",
                    "json",
                )
            )["items"]
            current = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
            require(len(current) == 1, "Expected exactly one current replica")
            component = "frontend" if name == "retailops-frontend" else "api"
            expected = release["images"][component]
            status = current[0]["status"]["containerStatuses"][0]
            require(
                status["ready"] and status["imageID"] == expected["cri_image_id"],
                "Running Pod image differs from loaded release",
            )
            result[name] = {
                "pod_uid": current[0]["metadata"]["uid"],
                "image_id": status["imageID"],
                "restart_count": status["restartCount"],
            }
        return result

    def validate(self, stage: str, expected: dict, release: dict) -> None:
        self.progress("Verify ingress, browser, data and image identities: " + stage)
        for path in ("/", "/api/health", "/api/ready"):
            self.until(lambda p=path: self.http(p) == 200, "Ingress path failed: " + path)
        checks = self.check("validate", data=expected)
        expected_file = self.report_dir / "expected.json"
        expected_file.write_text(json.dumps(expected))
        browser = json.loads(
            self.run(
                [
                    "node",
                    "scripts/release/browser-check.cjs",
                    self.url,
                    str(expected_file),
                    str(self.report_dir / stage),
                ]
            )
        )
        self.report["stages"][stage] = {
            "source_commit": release["source_commit"],
            "pods": self.identities(release),
            "api": checks,
            "browser": browser,
            "snapshot": expected["snapshot"],
        }

    def rollout(self, objects: list, release: dict) -> None:
        self.apply(
            [
                o
                for o in images_for(objects, release)
                if o["kind"] == "Deployment" and o["metadata"]["name"] in WORKLOADS
            ]
        )
        for name in WORKLOADS:
            self.wait(name)

    def network_policy(self) -> None:
        self.progress("Verify NetworkPolicy denial and allowed control")
        api_ip = self.get("service/retailops-api")["spec"]["clusterIP"]
        # Removing only the drill-owned checker label changes its policy membership.
        # Same Pod/image/URL: blocked -> allowed proves the denial is not an HTTP/DNS failure.
        self.k("-n", "retailops", "label", "pod/retailops-checker", "app.kubernetes.io/part-of-")
        self.until(
            lambda: not self.check("probe", api_ip)["reachable"], "Unlabelled Pod was not blocked"
        )
        self.k(
            "-n",
            "retailops",
            "label",
            "pod/retailops-checker",
            "app.kubernetes.io/part-of=retailops-platform",
        )
        self.until(
            lambda: self.check("probe", api_ip)["reachable"], "RetailOps Pod did not regain access"
        )
        foreign = copy.deepcopy(self.get("pod/retailops-checker"))
        foreign["metadata"] = {"name": "retailops-foreign-probe", "namespace": "default"}
        foreign.pop("status", None)
        foreign["spec"].pop("nodeName", None)
        foreign["spec"].pop("volumes", None)
        probe_container = foreign["spec"]["containers"][0]
        for field in ("volumeMounts", "envFrom", "env"):
            probe_container.pop(field, None)
        self.apply([foreign])
        self.k(
            "-n",
            "default",
            "wait",
            "pod/retailops-foreign-probe",
            "--for=condition=Ready",
            "--timeout=120s",
        )
        # With no egress policy in default, a direct IP failure tests API ingress denial.
        code = (
            "import socket\ns=socket.socket(); s.settimeout(3)\ntry:\n s.connect(("
            + repr(api_ip)
            + ",8000)); print('allowed')\nexcept OSError:\n print('blocked')"
        )
        result = self.k(
            "-n", "default", "exec", "retailops-foreign-probe", "--", "python", "-c", code
        ).strip()
        require(result == "blocked", "Foreign namespace could reach the API")
        self.report["network_policy"] = {
            "foreign_namespace_direct_ip": "blocked",
            "unlabelled_pod": "blocked",
            "retailops_pod": "allowed",
            "cni": "kindnet v1.0.1",
        }

    def database_restart(self) -> None:
        self.progress("Stop database; verify readiness removes API endpoints; restore same PVC")
        before = self.get("pods")["items"]
        api_pod = next(
            p
            for p in before
            if p["metadata"]["labels"].get("app.kubernetes.io/name") == "retailops-api"
        )
        db_uid = next(
            p["metadata"]["uid"]
            for p in before
            if p["metadata"]["labels"].get("app.kubernetes.io/name") == "postgres"
        )
        pvc = self.get("pvc/postgres-data")["metadata"]["uid"]
        self.k("-n", "retailops", "scale", "deployment/postgres", "--replicas=0")
        self.k(
            "-n",
            "retailops",
            "wait",
            "--for=delete",
            "pod",
            "-l",
            "app.kubernetes.io/name=postgres",
            "--timeout=120s",
        )
        self.until(
            lambda: self.get("deployment/retailops-api").get("status", {}).get("readyReplicas", 0)
            == 0,
            "API readiness stayed true during DB outage",
        )

        def endpoints_removed() -> bool:
            return not any(
                endpoint.get("conditions", {}).get("ready")
                for obj in self.get("endpointslices")["items"]
                if obj["metadata"]["labels"].get("kubernetes.io/service-name") == "retailops-api"
                for endpoint in obj.get("endpoints", [])
            )

        self.until(endpoints_removed, "Unready API is still an eligible endpoint")
        checks = self.check("db-outage", api_pod["status"]["podIP"])
        require(self.http("/api/ready") >= 500, "Ingress did not detect DB outage")
        self.k("-n", "retailops", "scale", "deployment/postgres", "--replicas=1")
        self.wait("postgres")
        self.wait("retailops-api")
        self.wait("retailops-realtime-consumer")
        after = next(
            p
            for p in self.get("pods")["items"]
            if p["metadata"]["labels"].get("app.kubernetes.io/name") == "postgres"
        )
        require(
            after["metadata"]["uid"] != db_uid
            and self.get("pvc/postgres-data")["metadata"]["uid"] == pvc,
            "Database did not restart on the original PVC",
        )
        self.report["database_restart"] = {
            **checks,
            "ready_api_endpoints_during_outage": 0,
            "new_pod_same_pvc": True,
        }

    def exercise(self, previous: dict, candidate: dict) -> None:  # noqa: PLR0915 -- ordered runtime drill
        require(
            previous["source_commit"] != candidate["source_commit"],
            "Distinct source commits required",
        )
        self.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                previous["source_commit"],
                candidate["source_commit"],
            ]
        )
        compatible(candidate, previous, previous["migration"]["head"])
        objects = self.render()
        initial = images_for(objects, previous)
        self.apply([o for o in initial if o["kind"] not in {"Deployment", "Job"}])
        self.apply(
            [
                o
                for o in initial
                if o["kind"] == "Deployment" and o["metadata"]["name"] in {"postgres", "redpanda"}
            ]
        )
        for name in ("postgres", "redpanda"):
            self.wait(name)
        for name in ("retailops-migrate", "retailops-seed-demo-data", "redpanda-topic-init"):
            self.apply([o for o in initial if o["kind"] == "Job" and o["metadata"]["name"] == name])
            self.k(
                "-n",
                "retailops",
                "wait",
                "--for=condition=complete",
                "job/" + name,
                "--timeout=240s",
            )
        self.report["jobs"] = {
            o["metadata"]["name"]: o["status"].get("succeeded", 0)
            for o in self.get("jobs")["items"]
        }
        self.rollout(objects, previous)
        self.checker(previous)
        self.start_forward()
        self.network_policy()
        self.report["streaming"] = self.check("stream")
        expected = self.check("prepare")
        self.validate("previous", expected, previous)
        self.database_restart()
        self.validate("database_restarted", expected, previous)
        # Broker data and consumer/API/frontend restart independently of database storage.
        broker_pvc = self.get("pvc/redpanda-data")["metadata"]["uid"]
        for name in ("redpanda", *WORKLOADS):
            self.k("-n", "retailops", "rollout", "restart", "deployment/" + name)
            self.wait(name)
        require(
            self.get("pvc/redpanda-data")["metadata"]["uid"] == broker_pvc, "Broker PVC changed"
        )
        self.validate("workloads_restarted", expected, previous)
        self.report["broker_topics"] = self.k(
            "-n",
            "retailops",
            "exec",
            "deployment/redpanda",
            "--",
            "rpk",
            "-X",
            "brokers=redpanda:9092",
            "topic",
            "list",
        ).splitlines()
        expected_topics = {
            "retailops." + name + ".v1"
            for name in ("sales", "inventory", "pricing", "intelligence", "operations", "dlq")
        }
        actual_topics = {line.split()[0] for line in self.report["broker_topics"] if line.strip()}
        require(expected_topics <= actual_topics, "Broker lost topics after restart")
        retained = self.k(
            "-n",
            "retailops",
            "exec",
            "deployment/redpanda",
            "--",
            "rpk",
            "-X",
            "brokers=redpanda:9092",
            "topic",
            "consume",
            "retailops.sales.v1",
            "-o",
            "start",
            "-n",
            "1",
            "-f",
            "%v",
        )
        require(
            json.loads(retained)["event_id"] == self.report["streaming"]["event_id"],
            "Broker lost the published message",
        )
        self.report["streaming"]["broker_message_retained_after_restart"] = True
        compatible(candidate, previous, self.check("head"))
        tick = time.monotonic()
        self.rollout(objects, candidate)
        self.validate("upgraded", expected, candidate)
        expected = self.check("write", "kubernetes-upgrade", data=expected)
        self.report["timings_seconds"]["upgrade_and_verification"] = round(
            time.monotonic() - tick, 3
        )
        self.k("-n", "retailops", "scale", "deployment/retailops-api", "--replicas=0")
        self.k(
            "-n",
            "retailops",
            "wait",
            "--for=delete",
            "pod",
            "-l",
            "app.kubernetes.io/name=retailops-api",
            "--timeout=120s",
        )
        require(self.http("/api/ready") == 502, "Injected API outage was not detected")
        self.report["negative_checks"]["api_outage"] = "HTTP 502 detected through ingress"
        compatible(candidate, previous, self.check("head"))
        tick = time.monotonic()
        self.rollout(objects, previous)
        self.validate("rolled_back", expected, previous)
        expected = self.check("write", "kubernetes-rollback", data=expected)
        self.report["timings_seconds"]["rollback_and_verification"] = round(
            time.monotonic() - tick, 3
        )
        self.report["final_snapshot"] = expected["snapshot"]
        self.report["database_head"] = self.check("head")
        self.report["migration_action"] = (
            "one initial migration/seed; same-history rollout; no downgrade/restore/reseed"
        )
        self.report["status"] = "passed"

    def cleanup(self) -> None:
        if self.forward:
            self.forward.terminate()
            self.forward.wait(timeout=10)
        if self.created:
            if self.config.exists():
                for args in (
                    ("get", "pods,pvc,jobs,deployments,ingress", "-o", "wide"),
                    ("get", "events", "--sort-by=.metadata.creationTimestamp"),
                ):
                    content = self.k("-n", "retailops", *args, allow_failure=True)
                    (
                        self.report_dir
                        / ("resources.txt" if args[1].startswith("pods") else "events.txt")
                    ).write_text(content)
                for name in ("postgres", "redpanda", *WORKLOADS):
                    (self.report_dir / (name + ".log")).write_text(
                        self.k(
                            "-n",
                            "retailops",
                            "logs",
                            "deployment/" + name,
                            "--all-containers",
                            "--tail=100",
                            allow_failure=True,
                        )
                    )
            self.run(
                [
                    "kind",
                    "delete",
                    "cluster",
                    "--name",
                    self.project,
                    "--kubeconfig",
                    str(self.config),
                ],
                stream=True,
            )
            require(
                self.project not in self.run(["kind", "get", "clusters"]).split(),
                "Cluster cleanup failed",
            )
        for tag in self.tags:
            self.run(["docker", "image", "rm", tag])
        self.report["cleanup"] = "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-ref", default=PREVIOUS)
    parser.add_argument("--candidate-ref", default="HEAD")
    parser.add_argument("--report-dir", default="ci-cd/reports/k8s-runtime")
    args = parser.parse_args()
    directory = Path(args.report_dir).resolve() / ("retailops-k8s-" + uuid4().hex[:10])
    directory.mkdir(parents=True)
    started = time.monotonic()
    with (
        (directory / "commands.log").open("w") as log,
        TemporaryDirectory(prefix="retailops-k8s-") as temp,
    ):
        drill = KubernetesDrill(directory, log, Path(temp))
        drill.report["harness_commit"] = drill.run(["git", "rev-parse", "HEAD"]).strip()
        drill.report["working_tree_dirty"] = bool(drill.run(["git", "status", "--porcelain"]))
        drill.report["harness_sha256"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "scripts/kubernetes").rglob("*.py"))
        }
        releases = {}
        try:
            releases["previous"] = drill.build(args.previous_ref, Path(temp) / "previous")
            releases["candidate"] = drill.build(args.candidate_ref, Path(temp) / "candidate")
            drill.create()
            for release in releases.values():
                drill.load_images(release)
            drill.preload_data_images()
            drill.exercise(releases["previous"], releases["candidate"])
        except Exception as error:  # noqa: BLE001 -- report failure after cleanup
            drill.report["error"] = str(error)
            drill.progress("Kubernetes drill failed: " + str(error))
        finally:
            try:
                drill.cleanup()
            except Exception as error:  # noqa: BLE001
                drill.report.update(status="failed", cleanup="failed", cleanup_error=str(error))
            drill.report["releases"] = releases
            drill.report["finished_at"] = datetime.now(UTC).isoformat()
            drill.report["timings_seconds"]["total"] = round(time.monotonic() - started, 3)
            (directory / "report.json").write_text(json.dumps(drill.report, indent=2) + "\n")
            drill.progress(
                f"Kubernetes drill {drill.report['status']}: {directory / 'report.json'}"
            )
    return 0 if drill.report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
