# Demo auth and RBAC boundary

## Purpose

RetailOps currently uses local demo identity to make role-aware UI, OpenAPI contracts and workflow boundaries visible before production authentication is implemented.

This is intentional portfolio scaffolding, not production authentication.

## What exists

- In-memory demo users and roles in `services/api/app/auth/roles.py`.
- Explicit permissions such as `workflow:write` and `notifications:write`.
- FastAPI checks that block unauthorized demo users from selected workflow and notification mutations.
- Identity endpoints that expose the local mock boundary through `GET /me` and `GET /me/permissions`.

## What does not exist yet

- Real login.
- Password handling.
- Sessions.
- JWT validation.
- OAuth/OIDC/SAML integration.
- Production RBAC or ABAC policy engine.
- Tenant isolation.
- IAM integration.

## Safe wording

Safe portfolio wording:

> Implemented explicit demo RBAC boundaries and permission checks for local workflow scenarios, with documented production-auth limitations.

Unsafe wording:

> Implemented production authentication and authorization.

## Recommended production path

1. Introduce OIDC provider integration, for example Cognito, Auth0, Okta or enterprise IdP.
2. Validate JWT issuer, audience, expiry and signature at API boundary.
3. Map claims to internal roles and permissions.
4. Move policy evaluation out of query parameters and into authenticated principal context.
5. Add audit logs for privileged workflow mutations.
6. Add negative tests for expired, malformed and wrong-audience tokens.

## Validation

```bash
cd services/api
PYTHONPATH=. pytest tests/test_demo_auth_boundary_readiness.py tests/test_notifications_api.py
```
