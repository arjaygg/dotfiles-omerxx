# Goal 02 — Add rate limiting to the public API

## Objective

Every public API endpoint enforces a per-client request rate limit and returns HTTP 429 with a `Retry-After` header when the limit is exceeded.

## Why

The public API currently has no request throttling, leaving the gateway exposed to abusive or runaway clients that can exhaust backend capacity and degrade service for everyone. Rate limiting protects availability and gives us a predictable ceiling on load.

## Current state

No rate limiting exists. All public endpoints accept unbounded request volume per client, and there is no mechanism to reject or slow excessive traffic.

## Non-goals

Not building per-tenant billing quotas or a distributed global limiter. This goal covers per-client rate limiting at the gateway only, not usage metering or plan-based tiers.

## Steps

1. Add a rate-limiting middleware keyed on client identity (API key or source IP) for public routes.
2. Reject requests over the configured limit with HTTP 429 and a `Retry-After` header.
3. Make the limit and window configurable via gateway config (with a sensible default).
4. Confirm the behavior in local dev: requests over the limit receive 429.

## Acceptance criteria

A local run of the gateway that sends requests above the configured limit to a public endpoint receives HTTP 429 responses with a `Retry-After` header, while requests under the limit succeed normally.

## Evidence to update

`plans/decisions.md` with the rate-limiting algorithm and storage chosen (e.g. token bucket, in-memory vs shared store).

## Stop and ask if

The rate limiter would require touching auth middleware, or would add a new production dependency (e.g. a shared cache/store) not already vendored.
