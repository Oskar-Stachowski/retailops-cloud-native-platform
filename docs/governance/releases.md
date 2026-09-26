# Release identity and registry promotion policy

`VERSION` contains the platform's `MAJOR.MINOR.PATCH` version. The current
release line is `0.2.1`. Existing `0.1.0` Docker labels were development labels,
not published Git releases. The API's OpenAPI version and frontend package
version are separate metadata; the release manifest identifies the platform.

## Build a candidate

```bash
make release-build
```

Requirements: Git history, Docker, Python 3.11+. The builder exports **committed**
API/frontend code with `git archive`; uncommitted source edits are never quietly
included. It builds both images with OCI source/revision/version labels and
writes a manifest under a unique `ci-cd/reports/releases/retailops-release-*/`
directory. Images remain available after a build-only run.

Manifest fields include:

- `manifest_version`, full source commit and `VERSION+git.<short-sha>`;
- API/frontend local tags, immutable image IDs and platform;
- Alembic head and hash of the complete migration history;
- explicit validation status and a CI run link when executed in GitHub Actions.

A `built_unverified` report or `not_yet_verified` manifest is **not approved for
release**. The drill changes validation to `local_drill_passed` only after its
checks pass. CI still needs to complete all required gates.

Local Docker `sha256:` image IDs identify artifacts in the current engine.
The manifest does not treat them as published registry digests or evidence of
registry publication, signing or SBOM attestation. Rebuilding a commit may produce a different image because
base tags and build metadata can change. Rollback uses the already-built image
IDs from the previous manifest; it never rebuilds or uses `latest`.

## Release/tag rules

1. Use PATCH for compatible fixes, MINOR for compatible capabilities and MAJOR
   for breaking public contracts; during 0.x, explicitly document any break.
2. Merge through the protected PR workflow and require successful `required-result`.
3. Complete the update/rollback drill for the chosen predecessor and candidate.
   Attach exact image identities, CI result, migration compatibility and evidence.
4. Only then create an annotated `vX.Y.Z` Git tag on the reviewed main commit.
   Never move or overwrite a published tag. A correction receives a new version.
5. Registry promotion is a separate operation: publish the same verified image
   artifacts, record registry digests, attach SBOM/provenance and retain the
   predecessor. A fresh rebuild is a new artifact requiring verification.

## Verified GHCR publication

The manually dispatched [release workflow](../../.github/workflows/release.yml)
publishes `ghcr.io/oskar-stachowski/retailops-cloud-native-platform-api` and
`ghcr.io/oskar-stachowski/retailops-cloud-native-platform-frontend`. The workflow
preserves package access settings. Anonymous digest reads of both packages were
verified for [v0.2.1](../evidence/releases/2026-09-26-registry.md).
Actions authenticates with its short-lived `GITHUB_TOKEN`.

It requires a clean, current protected-main commit, a new `VERSION`, an ancestor
predecessor and successful latest Required CI runs on main for both revisions.
The source pair is built once, exercised through update/failure/rollback, and
scanned using the repository's fixed-CRITICAL image policy. Trivy 0.74.0 generates
SPDX SBOMs from those exact images. Only then are the same local image IDs pushed;
no rebuild occurs between test and publication.

Registry tags include full source SHA, workflow run and attempt. They identify
publication attempts, are never used for deployment, and are not overwritten by
a retry. The manifest records the registry manifest digest separately from the
Docker engine image ID. Both the candidate and freshly built predecessor remain
in GHCR for the demonstrated rollback. This first release bootstraps a verified
predecessor; it does not claim to reuse an earlier published release artifact.

GitHub signs provenance and SBOM attestations for all four registry digests, and
signs the manifest binding their source revisions, migration fingerprints and
SBOM checksums. The provenance signer/source identifies the release workflow's
main commit (the harness); the signed manifest and OCI labels identify each
image's application source, including the older predecessor. No SLSA level or
reproducible-byte-build claim is made.

A separate fresh runner verifies the manifest, all image/SBOM signatures, exact
repository/workflow/main source identity, attached SBOM content and checksums.
It pulls by digest and binds the verified registry identity to the consumer's
engine-local image ID (which can differ between Docker storage backends), while
retaining the builder's ID in the report. It repeats the full drill without any image build. Only its
success permits an annotated `vX.Y.Z` tag and a published GitHub Release. The
release attaches a durable evidence bundle; intermediate Actions artifacts have
14-day retention. Failed partial publication is not a verified release.

The current workflow publishes native Linux AMD64 artifacts on GitHub-hosted
runners. Local ARM64 drill results are a separate platform; these do not establish
native ARM64 registry release coverage. Cloud deployment is a separate step.
See the [registry runbook](../runbooks/registry-release.md) and
[rollback runbook](../runbooks/application-rollback.md).
