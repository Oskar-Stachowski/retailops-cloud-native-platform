# ruff: noqa: INP001, S603
"""Promote tested images, then verify registry content on a separate runner."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

from release import require, verify_image

ROLES = ("previous", "candidate")
COMPONENTS = ("api", "frontend")
REPOSITORY = "Oskar-Stachowski/retailops-cloud-native-platform"
NAMESPACE = "ghcr.io/" + REPOSITORY.lower()
WORKFLOW = REPOSITORY + "/.github/workflows/release.yml"
TRIVY = "aquasec/trivy:0.74.0"


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, timeout=900)
    return result.stdout


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def images(manifest: dict) -> Iterator[tuple[str, str, dict, dict]]:
    for role in ROLES:
        release = manifest["releases"][role]
        for component in COMPONENTS:
            yield role, component, release, release["images"][component]


def ready_report(report: dict) -> None:
    require(report["status"] == "passed" and report["cleanup"] == "passed", "Drill did not pass")
    require(not report["working_tree_dirty"], "Release requires a clean committed harness")
    require(set(report["stages"]) == {"previous", "upgraded", "rolled_back"}, "Missing drill stage")
    for _, component, release, image in images(report):
        require(
            release["validation"] == "local_drill_passed", "Unverified image cannot be published"
        )
        inspected = json.loads(run(["docker", "image", "inspect", image["image_id"]]))[0]
        verify_image(inspected, release, component, image["image_id"])


def publication_contract(manifest: dict, report: dict) -> None:
    require(manifest["harness_commit"] == report["harness_commit"], "Harness identity changed")
    for role, component, release, image in images(manifest):
        tested = report["releases"][role]
        for key in ("source_commit", "version", "migration", "validation"):
            require(release[key] == tested[key], "Published source differs from tested source")
        for key in ("image_id", "tag", "platform"):
            require(
                image[key] == tested["images"][component][key], "Image differs from tested artifact"
            )


def prepare(report_path: Path, output: Path) -> None:
    report = read(report_path)
    ready_report(report)
    require(not output.exists(), "Output directory already exists")
    output.mkdir(parents=True)
    shutil.copyfile(report_path, output / "build-drill.json")
    for role, component, _, image in images(report):
        stem = role + "-" + component
        scanner = [
            "docker",
            "run",
            "--rm",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-v",
            str(output.resolve()) + ":/reports",
            "-v",
            str(output.resolve().parent / "trivy-release-cache") + ":/root/.cache/trivy",
            TRIVY,
            "image",
            "--image-src",
            "docker",
        ]
        run(
            [
                *scanner,
                "--scanners",
                "vuln",
                "--severity",
                "CRITICAL",
                "--ignore-unfixed",
                "--exit-code",
                "1",
                "--format",
                "json",
                "--output",
                "/reports/" + stem + "-scan.json",
                image["image_id"],
            ]
        )
        sbom = stem + ".spdx.json"
        run([*scanner, "--format", "spdx-json", "--output", "/reports/" + sbom, image["image_id"]])
        document = read(output / sbom)
        require(document.get("spdxVersion", "").startswith("SPDX-2."), "Invalid SPDX document")
        require(bool(document.get("packages")), "Empty image SBOM")
        image["sbom"] = {"file": sbom, "sha256": digest(output / sbom)}
    manifest = {
        "manifest_version": 2,
        "status": "tested_not_published",
        "repository": REPOSITORY,
        "harness_commit": report["harness_commit"],
        "ci_run_url": report["ci_run_url"],
        "releases": report["releases"],
        "scanner": {"image": TRIVY, "blocking": "fixed CRITICAL vulnerabilities"},
    }
    write(output / "release-manifest.json", manifest)


def registry_reference(repository: str, registry_digest: str) -> str:
    require(
        repository in {NAMESPACE + "-" + c for c in COMPONENTS}, "Unexpected registry repository"
    )
    require(re.fullmatch(r"sha256:[a-f0-9]{64}", registry_digest), "Invalid registry digest")
    return repository + "@" + registry_digest


def consumer_image(image: dict, inspected: dict, release: dict, component: str) -> dict:
    # Docker's classic and containerd stores may expose different engine-local IDs.
    # The registry digest identifies the portable artifact; bind it to this engine.
    require(image["registry_ref"] in inspected.get("RepoDigests", []), "Pulled digest differs")
    require(
        inspected["Os"] + "/" + inspected["Architecture"] == image["platform"], "Wrong platform"
    )
    verify_image(inspected, release, component, inspected["Id"])
    return {**image, "build_image_id": image["image_id"], "image_id": inspected["Id"]}


def publish(output: Path) -> None:
    manifest = read(output / "release-manifest.json")
    require(
        manifest["status"] == "tested_not_published", "Manifest already published or unverified"
    )
    report = read(output / "build-drill.json")
    publication_contract(manifest, report)
    ready_report(report)
    run_identity = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    require(re.fullmatch(r"\d+-\d+", run_identity), "Invalid workflow identity")
    for role, component, release, image in images(manifest):
        require(digest(output / image["sbom"]["file"]) == image["sbom"]["sha256"], "SBOM changed")
        repository = NAMESPACE + "-" + component
        tag = repository + ":sha-" + release["source_commit"] + "-run-" + run_identity
        run(["docker", "tag", image["image_id"], tag])
        pushed = run(["docker", "push", tag])
        matches = re.findall(r"digest: (sha256:[a-f0-9]{64})", pushed)
        require(len(matches) == 1, "Cannot establish the pushed manifest digest")
        reference = registry_reference(repository, matches[0])
        inspected = json.loads(run(["docker", "image", "inspect", reference]))[0]
        verify_image(inspected, release, component, image["image_id"])
        image.update(
            registry_repository=repository,
            registry_digest=matches[0],
            registry_ref=reference,
            registry_tag=tag,
        )
        if os.getenv("GITHUB_OUTPUT"):
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as handle:
                handle.write(f"{role}_{component}_name={repository}\n")
                handle.write(f"{role}_{component}_digest={matches[0]}\n")
    manifest["status"] = "published_pending_pull_verification"
    write(output / "release-manifest.json", manifest)


def verify_attestation(subject: str, bundle: Path, manifest: dict, predicate: str) -> list:
    result = run(
        [
            "gh",
            "attestation",
            "verify",
            subject,
            "--bundle",
            str(bundle),
            "--repo",
            REPOSITORY,
            "--signer-workflow",
            WORKFLOW,
            "--source-digest",
            manifest["harness_commit"],
            "--source-ref",
            "refs/heads/main",
            "--deny-self-hosted-runners",
            "--predicate-type",
            predicate,
            "--format",
            "json",
        ]
    )
    return json.loads(result)


def pull(output: Path) -> None:
    manifest_path = output / "release-manifest.json"
    manifest = read(manifest_path)
    require(manifest["repository"] == REPOSITORY, "Wrong source repository")
    require(manifest["status"] == "published_pending_pull_verification", "Wrong publication stage")
    require(manifest["harness_commit"] == os.environ["GITHUB_SHA"], "Unexpected release source")
    verify_attestation(
        str(manifest_path),
        output / "manifest-provenance.jsonl",
        manifest,
        "https://slsa.dev/provenance/v1",
    )
    for role, component, release, image in images(manifest):
        reference = registry_reference(image["registry_repository"], image["registry_digest"])
        require(reference == image["registry_ref"], "Registry reference was changed")
        require(digest(output / image["sbom"]["file"]) == image["sbom"]["sha256"], "SBOM changed")
        stem = role + "-" + component
        verify_attestation(
            "oci://" + reference,
            output / (stem + "-provenance.jsonl"),
            manifest,
            "https://slsa.dev/provenance/v1",
        )
        verified = verify_attestation(
            "oci://" + reference,
            output / (stem + "-sbom.jsonl"),
            manifest,
            "https://spdx.dev/Document",
        )
        require(
            any(
                v["verificationResult"]["statement"]["predicate"]
                == read(output / image["sbom"]["file"])
                for v in verified
            ),
            "Signed SBOM does not match the attached document",
        )
        # On a fresh runner no local release build is available; pull only the signed digest.
        run(["docker", "pull", "--platform", image["platform"], reference])
        inspected = json.loads(run(["docker", "image", "inspect", reference]))[0]
        release["images"][component] = consumer_image(image, inspected, release, component)
    for role in ROLES:
        write(output / (role + "-manifest.json"), manifest["releases"][role])
    write(
        output / "pull-verification.json",
        {
            "status": "passed",
            "harness_commit": manifest["harness_commit"],
            "images": 4,
            "provenance_and_sbom_signatures_verified": True,
            "signed_manifest_sha256": digest(manifest_path),
        },
    )


def complete(output: Path, report_path: Path) -> None:
    report = read(report_path)
    require(
        report["status"] == "passed" and report["cleanup"] == "passed", "Pulled-image drill failed"
    )
    manifest = read(output / "release-manifest.json")
    require(
        read(output / "pull-verification.json")["status"] == "passed",
        "Missing signature/pull check",
    )
    for role in ROLES:
        consumed = read(output / (role + "-manifest.json"))
        for component in COMPONENTS:
            signed_image = manifest["releases"][role]["images"][component]
            runtime_image = consumed["images"][component]
            require(
                runtime_image["build_image_id"] == signed_image["image_id"],
                "Build identity changed",
            )
            require(
                {key: runtime_image[key] for key in signed_image if key != "image_id"}
                == {key: value for key, value in signed_image.items() if key != "image_id"},
                "Consumer changed the signed image contract",
            )
            require(
                report["releases"][role]["images"][component] == runtime_image,
                "Runtime tested a different image",
            )
    shutil.copyfile(report_path, output / "registry-drill.json")
    write(
        output / "release-verification.json",
        {
            "status": "verified",
            "manifest_sha256": digest(output / "release-manifest.json"),
            "registry_drill_sha256": digest(output / "registry-drill.json"),
            "source_commit": manifest["harness_commit"],
            "ci_run_url": manifest["ci_run_url"],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "publish", "pull", "complete"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.report, args.output)
    elif args.action == "publish":
        publish(args.output)
    elif args.action == "pull":
        pull(args.output)
    else:
        complete(args.output, args.report)
    sys.stdout.write(f"Registry {args.action}: passed\n")


if __name__ == "__main__":
    main()
