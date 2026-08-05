# Goal 02 — Add rate limiting to the public API

## Objective

Every public API endpoint enforces a per-client request-rate limit, returning HTTP 429 with a `Retry-After` header once a client exceeds its configured allowance.

## Why

The public API currently has no rate limiting, so a single misbehaving or abusive client can exhaust gateway capacity and degrade service for everyone. A per-client limit protects availability and gives us a lever to shape traffic without code changes per incident.

## Current state

No rate limiting exists on any route. All requests are served unconditionally; there is no per-client accounting, no 429 responses, and no configuration surface for limits.

## Non-goals

Not building distributed/global rate limiting across multiple gateway instances, and not adding per-endpoint quota tiers or billing-plan enforcement. This goal is a single per-client rate limit applied to public routes only. Internal/admin routes and auth middleware are out of scope.

## Steps

1. Choose an in-process rate-limit strategy (e.g. token bucket) and a client-identity key (API key or source IP) for public routes.
2. Add rate-limit middleware that applies only to public endpoints, leaving internal/admin routes untouched.
3. On limit exceeded, return HTTP 429 with a `Retry-After` header and a structured JSON error body.
4. Make the limit (requests per window) configurable via the existing deploy-pipeline config, with a safe default.
5. Confirm behavior in local dev: requests under the limit succeed; requests over the limit return 429.

## Acceptance criteria

A local run of the gateway shows: requests below the configured limit for a client return normal responses, and once the limit is exceeded the same client receives HTTP 429 with a `Retry-After` header. Internal/admin routes remain unthrottled. The limit value is read from config, not hard-coded.

## Evidence to update

`plans/decisions.md` with the chosen rate-limit strategy, the client-identity key, and the default limit value.

## Stop and ask if

The rate-limit strategy would require a new shared datastore (e.g. Redis) not already provisioned, or the change would touch the auth middleware — per the global guardrails, stop and ask before touching auth.
