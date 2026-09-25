# Local release identity and promotion policy

`VERSION` contains the platform's next `MAJOR.MINOR.PATCH` version. The current
candidate line is `0.2.0`. Existing `0.1.0` Docker labels were development labels,
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

This change establishes local candidate builds and rollback evidence. It does
not create a public Git release, publish images or deploy a cloud environment.
The [rollback runbook](../runbooks/application-rollback.md) defines the migration
boundary and executable drill.
