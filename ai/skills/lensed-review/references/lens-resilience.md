# Resilience Lens

Derived from `hawk`'s Resilience dimension and the `silent-failure-hunter` agent. Runs when the
change touches error handling, retries, external calls, or concurrency (see `lenses.toml`).

## What to check

- **Swallowed errors**: caught exceptions/errors that are logged-and-ignored, or ignored outright,
  where the caller has no way to know the operation failed.
- **Bad fallbacks**: a failure path that silently substitutes a default value or empty result
  instead of surfacing the failure, when that default could mask a real problem downstream.
- **Missing error propagation**: a function that swallows an error from a dependency instead of
  returning/raising it, breaking the caller's ability to react.
- **External call resilience**: network/API/DB calls without timeouts, retries, or circuit
  breaking where the call is on a critical path and failure is plausible.
- **Concurrency safety**: shared mutable state accessed without synchronization; goroutine/thread
  leaks from unclosed channels or unjoined threads; race conditions from unordered writes.

## Process

1. Trace every error-handling branch in the diff — `catch`/`except`/`if err != nil`/similar. For
   each, confirm what happens to the error: propagated, logged-and-swallowed, or silently dropped.
2. For external calls, confirm timeout/retry behavior exists and is appropriate to the call's
   criticality — not every call needs a circuit breaker, but calls on a request's critical path
   generally need at least a timeout.
3. Emit one finding per confirmed issue: `lens: "resilience"`, `location`, `trigger_condition` (the
   specific input/state that triggers the failure), `guard_snippet` (concrete fix — propagate the
   error, add a timeout, add a lock), `potential_consequence` (what breaks silently, and how a user
   or operator would discover it, if ever). No `severity` field.
4. A "mysterious behavior" bug report is a strong signal to apply this lens even outside a formal
   review — silent failures are exactly what produces reports like that.
