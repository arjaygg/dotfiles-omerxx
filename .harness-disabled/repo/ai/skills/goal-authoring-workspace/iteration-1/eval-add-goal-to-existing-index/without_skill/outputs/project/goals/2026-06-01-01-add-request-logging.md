# Goal 01 — Add structured request logging

## Objective

Every inbound API request logs method, path, status, and latency as structured JSON.

## Why

Support needs to correlate customer-reported errors with gateway behavior; today there's no per-request log line.

## Current state

No request-level logging exists. Only startup/shutdown logs are emitted today.

## Non-goals

Not building a full observability/tracing stack — just structured per-request log lines.

## Steps

1. Add a logging middleware that wraps every request.
2. Emit one JSON line per request with method, path, status, latency_ms.
3. Confirm log lines appear in local dev.

## Acceptance criteria

A local run of the gateway against any endpoint produces one JSON log line per request with all four fields.

## Evidence to update

`plans/decisions.md` with the logging library chosen.

## Stop and ask if

The chosen logging library would add a new production dependency not already vendored.
