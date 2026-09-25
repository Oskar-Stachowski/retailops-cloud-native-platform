# ruff: noqa: INP001, S603
"""Gate a manual main-branch release and publish its verified evidence."""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from registry import REPOSITORY, digest, read, run, write
from release import require


def api(path: str, *, data: dict | None = None, missing_ok: bool = False) -> object:
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPOSITORY + "/" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed GitHub API
            return json.load(response)
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise


def passed_main_run(runs: list, sha: str) -> dict:
    matching = [
        r
        for r in runs
        if r["head_sha"] == sha
        and r["head_branch"] == "main"
        and r["event"] in {"push", "workflow_dispatch"}
    ]
    require(bool(matching), "No Required CI main run for source commit")
    latest = max(matching, key=lambda r: (r["run_number"], r["run_attempt"]))
    require(
        latest["status"] == "completed" and latest["conclusion"] == "success",
        "Latest Required CI main run did not pass",
    )
    return {"id": latest["id"], "head_sha": sha, "html_url": latest["html_url"]}


def preflight(previous: str, output: Path) -> None:
    require(os.environ["GITHUB_REF"] == "refs/heads/main", "Release only from protected main")
    require(os.environ["GITHUB_REPOSITORY"] == REPOSITORY, "Unexpected repository")
    sha = os.environ["GITHUB_SHA"]
    require(
        run(["git", "rev-parse", "HEAD"]).strip() == sha, "Checkout differs from selected source"
    )
    require(not run(["git", "status", "--porcelain"]).strip(), "Working tree is not clean")
    require(
        api("git/ref/heads/main")["object"]["sha"] == sha, "Main moved; select its latest commit"
    )
    require(re.fullmatch(r"[a-f0-9]{40}", previous), "Use a full predecessor commit SHA")
    require(previous != sha, "Predecessor must differ from candidate")
    run(["git", "merge-base", "--is-ancestor", previous, sha])
    version = Path("VERSION").read_text().strip()
    require(re.fullmatch(r"\d+\.\d+\.\d+", version), "Invalid version")
    require(api("git/ref/tags/v" + version, missing_ok=True) is None, "Release tag already exists")
    require(api("releases/tags/v" + version, missing_ok=True) is None, "Release already exists")
    evidence = {}
    for role, commit in (("previous", previous), ("candidate", sha)):
        runs = api("actions/workflows/required-ci.yml/runs?per_page=100&head_sha=" + commit)[
            "workflow_runs"
        ]
        evidence[role] = passed_main_run(runs, commit)
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, {"status": "passed", "version": version, "required_ci": evidence})


def finish(output: Path) -> None:
    manifest = read(output / "release-manifest.json")
    verification = read(output / "release-verification.json")
    require(verification["status"] == "verified", "Registry verification is not complete")
    require(
        verification["manifest_sha256"] == digest(output / "release-manifest.json"),
        "Manifest changed",
    )
    require(
        verification["registry_drill_sha256"] == digest(output / "registry-drill.json"),
        "Report changed",
    )
    sha = manifest["harness_commit"]
    require(sha == os.environ["GITHUB_SHA"], "Release source mismatch")
    require(api("git/ref/heads/main")["object"]["sha"] == sha, "Main moved before promotion")
    version = manifest["releases"]["candidate"]["version"].split("+")[0]
    tag = "v" + version
    require(api("git/ref/tags/" + tag, missing_ok=True) is None, "Never overwrite a release tag")
    require(api("releases/tags/" + tag, missing_ok=True) is None, "Never overwrite a release")
    lines = [
        f"RetailOps {tag}",
        "",
        f"Source: `{sha}`",
        f"Workflow: {manifest['ci_run_url']}",
        "",
        "The same Linux amd64 images passed the build-side and fresh-runner registry rollback drills.",
        "All four images have verified GitHub provenance and signed SPDX SBOMs.",
        "",
        "| Role | Component | Immutable registry reference |",
        "|---|---|---|",
    ]
    for role in ("candidate", "previous"):
        for component, image in manifest["releases"][role]["images"].items():
            lines.append(f"| {role} | {component} | `{image['registry_ref']}` |")
    lines += [
        "",
        "The previous pair is a bootstrapped, freshly tested rollback baseline, not a previously published release.",
        "GHCR packages retain their current access settings; first publication defaults to private.",
        "The application remains a local demo with same-schema rollback. No cloud deployment or production RTO is claimed.",
        "Download the evidence bundle for manifests, signed bundles, SBOMs, scans, CI references and both drill reports.",
    ]
    notes = output / "release-notes.md"
    notes.write_text("\n".join(lines) + "\n")
    sums = output / "SHA256SUMS"
    sums.write_text(
        "".join(
            f"{digest(p)}  {p.name}\n"
            for p in sorted(output.iterdir())
            if p.is_file() and p != sums
        )
    )
    archive = output.parent / ("retailops-" + tag + "-evidence.tar.gz")
    run(["tar", "-czf", str(archive), "-C", str(output), "."])
    annotated = api(
        "git/tags",
        data={
            "tag": tag,
            "message": "Verified RetailOps release " + tag,
            "object": sha,
            "type": "commit",
        },
    )
    api("git/refs", data={"ref": "refs/tags/" + tag, "sha": annotated["sha"]})
    # An incomplete upload remains a draft; reruns never overwrite tags or releases.
    run(
        [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            REPOSITORY,
            "--verify-tag",
            "--draft",
            "--title",
            "RetailOps " + tag,
            "--notes-file",
            str(notes),
        ]
    )
    run(
        [
            "gh",
            "release",
            "upload",
            tag,
            "--repo",
            REPOSITORY,
            str(archive),
            str(output / "release-manifest.json"),
            str(sums),
        ]
    )
    run(["gh", "release", "edit", tag, "--repo", REPOSITORY, "--draft=false"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "finish"))
    parser.add_argument("--previous-ref")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "preflight":
        preflight(args.previous_ref, args.output)
    else:
        finish(args.output)


if __name__ == "__main__":
    main()
