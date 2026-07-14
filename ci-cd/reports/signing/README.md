# Signing evidence

Cosign signature verification output belongs here after a registry-backed
release image exists.

Expected examples:

```text
cosign-api-verify.txt
cosign-frontend-verify.txt
```

Current status:

- Cosign identity policy is documented in `security/signing/`.
- No signed release image verification output is committed yet.
- Do not claim signed release images until these files are generated from
  immutable image digests.
