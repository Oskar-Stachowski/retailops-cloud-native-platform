# Immutable source bundle transfer

AI10 is in progress. This interface distributes an existing immutable facts-only
Source Snapshot 1.0/1.1/1.2 export. It does not create a live database snapshot,
establish a broker offset boundary, implement replay, or qualify any ML model.
The bounded `/integration/v2` capability contract remains unchanged; its snapshot
operation still refuses unsupported snapshot/replay requests.

## Publish and grant access

1. Obtain an approved complete export, including `snapshot_manifest.json`,
   `manifest.sha256`, facts, schemas, reports and copied source manifests. Keep
   evaluation truth outside this directory. The publisher seals physical bytes;
   the receiving AI importer separately checks typed data, logical identities,
   namespace and source qualification for the requested use case.
2. As the API's operating-system user, from `services/api`, run:

   ```sh
   python -m scripts.publish_source_bundle --snapshot-dir /approved/export --store /private/bundles
   ```

   Preserve the returned `bundle_id`, original `snapshot_id` and
   `source_dataset_id`. The new bundle identity hashes the complete byte
   inventory and does not replace the source's logical identity. Existing
   identical publications are verified and reused; conflicting bytes, even an
   existing empty destination, are never overwritten. Keep the store on a local
   filesystem supporting atomic no-replace publication and fsync.
3. Keep the store owned by the API user, with directory mode 0700 and file mode
   0600. Symlinks, hard links, undeclared files, unsafe paths, corrupt bytes and
   exports containing evaluation truth are rejected. Limits are 64 MiB per
   file, 2 GiB total and 10,000 declared files.
4. Generate a separate random bearer credential using the deployment secret
   manager. Hash its UTF-8 bytes with SHA-256 and create a private JSON policy,
   owned by the API user with mode 0600:

   ```json
   {
     "version": "retailops-source-bundle-access-1.0",
     "principals": [{
       "principal_id": "ai-source-reader",
       "credential_sha256": "<64 lower-case hexadecimal characters>",
       "bundle_ids": ["<explicit published bundle_id>"]
     }]
   }
   ```

   A grant authorizes every file in the named bundle. A product-scoped bounded
   REST credential does not grant access to a bundle; a bundle credential does
   not grant bounded REST access. Never infer permission to distribute the full
   source from a product-level grant.
5. Configure `RETAILOPS_SOURCE_BUNDLE_ROOT=/private/bundles` and
   `RETAILOPS_SOURCE_BUNDLE_ACCESS_POLICY=/private/bundle-policy.json` in the
   API deployment. Mount the store and policy read-only and provide HTTPS.
   Without a configured valid policy access is denied. Policy is read afresh on
   every request, so credential revocation takes effect on the next request.
6. With the assigned credential, read
   `GET /integration/bundles/v1/{bundle_id}/manifest` and then each declared
   `GET /integration/bundles/v1/{bundle_id}/files/{file_id}`. The latter returns
   exact bytes, a digest ETag and `Cache-Control: no-store`. It never accepts a
   user-supplied filesystem path. Unauthorized requests fail before storage
   lookup (401/403); missing granted objects return 404 and unsafe or corrupted
   store objects fail closed with 503.
7. Use the pinned AI bundle CLI and its private configuration to download and
   import the entire inventory, with the required use case specified explicitly.
   Inspect its typed verification receipt and preserve source IDs. A successful
   byte transfer alone is not a source or model qualification.

## Acceptance and failure handling

Run `services/api/tests/test_source_bundles.py` for authorization, revocation,
file confinement, byte checks and atomic/concurrent publication. The required
cross-repository CI gate generates a native 1.2 export using an immutable
producer owner and runs the actual receiving importer over HTTP; its receipt
records pins and both first and repeated import results. No existing session,
model environment or local Docker daemon is used by that gate.

If download, timeout, identity, schema, logical checksum or use-case validation
fails, do not approve the import. Investigate the approved original export and
its receipt. Publish a corrected export under its new identity and grant that
identity explicitly; do not repair sealed bytes in place. Keep credentials out
of URLs, command arguments, logs, commits and evidence artifacts.
