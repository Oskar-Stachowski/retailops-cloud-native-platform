# Verified registry release

The workflow publishes a reviewed pair of API/frontend versions to GHCR and
proves update/rollback using fresh digest pulls. It uses one temporary demo
database per drill, never the workstation's RetailOps data.

## Start a release

1. Set the next unused SemVer in `VERSION`; merge through the protected PR flow.
2. Wait for Required CI on that exact **main** commit to succeed. The selected
   predecessor must also have a successful latest Required CI main run.
3. Open Actions → **Verified registry release** → Run workflow, choose `main`,
   and provide the predecessor's full SHA. The initial default is
   `cb0c79848247612bf71fb9ccf63a8ff3847b5ca1` (the verified local rollback foundation).
   Both versions must have identical migration history and a supported schema.
4. Review the three jobs: build/test/scan/publish/attest; fresh pull/signature
   verification/runtime drill; final annotated tag and release publication.
5. Use the GitHub Release's `release-manifest.json` and evidence archive as the
   delivery record. The presence of an image tag alone is not release approval.

Equivalent authenticated CLI invocation:

```bash
gh workflow run release.yml --ref main -f previous_ref=<full-main-commit-SHA>
```

No permanent PAT or registry secret is needed by Actions. New packages default
to private. An external machine needs GitHub Packages read access and Docker
authentication to pull them; do not paste tokens into commands, logs or files
tracked by Git. Use `docker login ghcr.io --password-stdin` with an appropriately
scoped credential supplied through your normal secret-handling mechanism.

## Retrieve and verify

The evidence bundle contains the signed registry manifest, four SPDX SBOMs,
four image provenance bundles, four signed SBOM bundles, scanner results,
Required CI references, build-side and registry-side drill reports, and checksums.
The separate `release-verification.json` binds successful registry verification
to the immutable signed manifest; it does not modify that signed manifest.

Verify checksums from inside the extracted evidence directory. Checksums detect
accidental changes; authenticity comes from the signature verification below.

```bash
shasum -a 256 -c SHA256SUMS
gh attestation verify release-manifest.json \
  --bundle manifest-provenance.jsonl \
  --repo Oskar-Stachowski/retailops-cloud-native-platform \
  --signer-workflow Oskar-Stachowski/retailops-cloud-native-platform/.github/workflows/release.yml \
  --source-ref refs/heads/main --source-digest <release-source-SHA>
docker pull --platform linux/amd64 <registry-repository>@sha256:<digest-from-manifest>
```

For the automated four-image verification and demo drill, check out the exact
release source, install locked frontend dependencies and Chromium as described
in the [rollback runbook](application-rollback.md), and extract the bundle to an
ignored directory such as `ci-cd/reports/registry-replay/`. With authenticated
`gh` and Docker:

```bash
GITHUB_SHA=<release-source-SHA> python3 scripts/release/registry.py pull \
  --output ci-cd/reports/registry-replay
python3 scripts/release/drill.py \
  --previous-manifest ci-cd/reports/registry-replay/previous-manifest.json \
  --candidate-manifest ci-cd/reports/registry-replay/candidate-manifest.json
```

`registry.py pull` enforces the signer workflow, source commit/ref, digest,
SBOM signature/content, OCI labels and Docker image identity. Imported manifests
also must match migration fingerprints and version metadata exported from Git.
There is no fallback to mutable tags or to a local image build.

## Failure handling

- A failed preflight, runtime drill, vulnerability scan or SBOM generation blocks
  image publication. Failed attestation/pull/rollback blocks the release.
- A partial publish can leave unpromoted run-specific image tags in GHCR. Retain
  them for diagnosis; a new workflow attempt uses distinct tags. Never present
  such an attempt as a successful release or silently rewrite its identity.
- A failure during final tag/upload can leave an annotated tag and draft release.
  Inspect the recorded run and repair its missing attachments explicitly; the
  workflow refuses to overwrite an existing tag/release. Do not delete or move
  a published version to make a retry pass.
- If main advances during a run, final promotion is refused. Review a new version
  against the new main rather than promoting an unreviewed checkout.
- Preserve the predecessor digests and evidence for every retained release.
  This first workflow tests a freshly built predecessor from an approved commit;
  it is not a production controller automatically selecting a historical release.

Successful small-fixture drills establish neither production RTO/RPO nor safe
rollback across schema or data-semantic changes. The release remains a local
demo application; registry publication does not deploy a cloud environment.
