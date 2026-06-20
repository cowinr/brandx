---
title: "API Gateway: Design Decision Record"
subtitle: "Authentication architecture review — Phase 1"
date: 2026-06-20
---

## Context

Our services currently authenticate requests at the application layer, with each service implementing its own token validation logic. This works, but it scatters a cross-cutting concern across a dozen codebases and means every new service has to re-solve the same problem.

This note captures the decision to centralise authentication at the gateway layer and the reasoning behind the chosen approach.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Per-service JWT validation | Already in place; no migration | Logic duplicated; drift inevitable |
| Shared auth library | Single implementation | Still deployed 12 times; versioning risk |
| API Gateway (centralised) | One place to change; clear separation | New infrastructure; latency budget |

> [!NOTE]
> Latency figures in the table above assume an in-region auth service. Cross-region calls add ~40 ms and are not acceptable on the synchronous request path.

## Decision

Centralise at the gateway. Each service receives a pre-validated claims header and trusts it without re-checking the token. The gateway is the only component that holds the signing keys.

The gateway pattern also opens the door to rate limiting, request logging, and A/B routing without modifying any downstream service.

> [!TIP]
> If you are adding a new service, register its route in `gateway/routes.yaml` and declare the required claims in `gateway/policies/<service>.yaml`. The gateway handles the rest.

## Implementation plan

1. Deploy the gateway in shadow mode alongside existing auth (no traffic routed yet).
2. Migrate one low-risk service to validate the claims header pattern.
3. Run both paths in parallel for two weeks; compare error rates.
4. Promote the gateway to primary; decommission per-service validation after a further four weeks.

> [!WARNING]
> Do not remove per-service validation until step 4 is complete and all services have been migrated. Running the gateway without a fallback during migration is a single point of failure.

## Code reference

The gateway auth middleware lives in `src/gateway/middleware/auth.py`. The core validation looks like this:

```python
def validate_token(token: str, public_key: str) -> dict:
    """Validate a JWT and return the decoded claims dict."""
    try:
        return jwt.decode(token, public_key, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}")
```

Call this from the middleware before forwarding the request. The returned claims dict is serialised into the `X-Auth-Claims` header that downstream services consume.

## Status

Work in progress. The shadow-mode deployment is complete. Service migration begins next sprint.

> The goal is one enforcement point, not twelve. Simpler to audit, simpler to change.
