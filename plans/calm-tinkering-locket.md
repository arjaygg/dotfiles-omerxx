# RFC: Resilient Mid‑Session Model Fallback for Gemini Backend (Proxy‑Layer)

## Context
Today, `claude-gemini` launches Claude Code with ANTHROPIC_BASE_URL pointing to CLIProxyAPI on 127.0.0.1:8317. When the selected Gemini model (e.g., gemini‑2.5‑pro) hits quota or returns 5xx/timeouts mid‑session, the session errors until the user manually switches models. We want automatic, transparent fallback during invocation without user action, preserving the existing aliases and UX.

Constraints and current wiring:
- Launcher: ~/.dotfiles/.claude/scripts/claude-launch.sh sets ANTHROPIC_BASE_URL and defaults CLAUDE_CODE_MODEL, then execs `claude`.
- Ports: 8317 (Gemini), 8318 (Codex), 8319 (Cursor), 8320 (Router). Cursor sidecar on 8005.
- CLIProxyAPI configs live at ~/.config/cliproxyapi/*.yaml, not tracked in repo.
- Logs: /tmp/cliproxy-<port>.log. No existing fallback/retry logic in repo.

## Goal
Provide mid‑session, per‑request fallback across a prioritized list of Gemini models (e.g., pro → flash → flash‑lite → 3‑pro‑preview) when the current model returns 429/5xx/timeout, with minimal disruption to current aliases and launcher.

---

## Option A — Local Fallback Gateway in front of CLIProxy (Recommended)
Introduce a tiny gateway that binds to the same port `claude-gemini` uses (8317) and proxies Anthropic-compatible /v1/messages and /v1/models requests:

Behavior
- For each POST /v1/messages:
  - Try candidate models in order: [gemini‑2.5‑pro, gemini‑2.5‑flash, gemini‑2.5‑flash‑lite, gemini‑3‑pro‑preview]. For each attempt:
    - Rewrite `model` in the request body to the candidate.
    - Forward to an upstream (either current CLIProxyAPI on an alternate port or directly to provider).
    - If 2xx, return response immediately (include a response header like `x-fallback-model` for observability).
    - If 429/>=500/timeout, continue to next candidate.
  - If all fail, return the last error.
- For GET /v1/models: return the union of available candidates, marking the preferred order.

Integration
- Keep the current alias and launcher untouched.
- Take the port (8317) so the launcher’s `start_proxy` lsof check won’t start CLIProxyAPI on that port. The gateway can:
  - run its own CLIProxyAPI instance on a different port (e.g., 9317) and forward to it, or
  - call provider APIs directly using existing auths.

Pros
- True mid‑session automatic failover with no user interaction.
- Zero change to aliases and minimal launcher awareness.
- Extensible to Codex/ Cursor later.

Cons
- New component to maintain (small service).
- Must handle Anthropic-compatible streaming if used (SSE chunking) and preserve headers.

Key Work Items
- Implement gateway (Go/FastAPI/Node) with:
  - Configurable candidate list and per-attempt timeout (e.g., 8–12s).
  - Error classification (429, 5xx, network timeout) as retryable.
  - Streaming passthrough support if needed.
  - Simple metrics/logging: chosen model, attempt count, latency.
- Modify launcher’s gemini branch only if needed to set an alternate upstream port; preferred is to keep current env and let the gateway own 8317.
- Validate with curl/CLI smoke tests.

---

## Option B — CLIProxyAPI Virtual Model with Fallback (If Supported)
Attempt to configure ~/.config/cliproxyapi/gemini.yaml to define a virtual alias (e.g., `gemini-auto`) that maps to multiple upstream models with an ordered fallback policy.

Behavior
- Keep ANTHROPIC_BASE_URL pointing at CLIProxyAPI on 8317.
- Set CLAUDE_CODE_MODEL to `gemini-auto`.
- CLIProxyAPI selects the first healthy model for each request, falling back on 429/5xx/timeout.

Pros
- No new component; managed entirely by CLIProxyAPI.
- Minimal code and operational overhead.

Cons
- Depends on CLIProxyAPI supporting ordered fallback semantics for a single alias; not present in current configs/docs.
- If unsupported, we’d end up re-implementing fallback inside CLIProxyAPI via custom plugin or forking (larger effort).

Key Work Items
- Verify CLIProxyAPI capabilities for multi-target alias with fallback.
- If supported, update gemini.yaml and test; if not, revert to Option A.

---

## Option C — Assisted In-Session Fallback (Least Robust)
Provide fast manual recovery: on error 429/5xx, a helper command switches to the next model (e.g., `/model gemini-2.5-flash`). Could be aided by a small script that checks 8317 and prints a recommended next model.

Pros
- Trivial to add; no infra changes.

Cons
- Requires user action; does not meet “automatic mid‑session” requirement.

---

## Recommendation
Proceed with Option A: Local fallback gateway in front of CLIProxy for Gemini.

Rationale
- Guarantees mid‑session failover with no user involvement.
- Keeps existing aliases and launcher intact.
- Independent of CLIProxyAPI’s internal feature set.
- Extensible: the same gateway can be reused for Codex/ Cursor in the future.

---

## High-Level Design (Option A)
- Port binding: Gateway listens on 127.0.0.1:8317.
- Upstream: Start CLIProxyAPI (current gemini.yaml) on 9317 (adjust launcher only if we choose to auto-start that instance; otherwise, keep current instance and forward directly to provider using the existing auth-dir files).
- Request flow (messages):
  - Parse JSON; capture original model.
  - For candidate in priority list:
    - Set body.model = candidate.
    - POST to upstream /v1/messages with same headers (x-api-key, anthropic-version).
    - If status 2xx: add `x-fallback-model: <candidate>`, return.
    - If 429/5xx/network timeout: continue.
  - If all fail: return the last error JSON.
- Request flow (models):
  - Proxy upstream /v1/models and ensure all candidate IDs appear; add `preferred_order` metadata if desired.
- Streaming:
  - If CLI session uses streaming, use a streaming-capable HTTP client and relay SSE chunks line-by-line. Only change model between full attempts; don’t mix streams.
- Telemetry:
  - Log structured event per request: model_attempts, chosen_model, status, latency_per_attempt.

---

## Risks and Mitigations
- Streaming complexity → start with non-streaming; add streaming after validation.
- Ambiguous errors → treat 4xx other than 429 as non-retryable; retry 429, 5xx, timeouts.
- Model compatibility → candidate list restricted to compatible Gemini family models.

---

## Verification Plan
- Unit curl tests against 8317:
  - /v1/models returns expected models.
  - /v1/messages with model=gemini-2.5-pro while upstream is rate-limited returns from gemini-2.5-flash with x-fallback-model header.
- CLI smoke tests:
  - claude-gemini; /model gemini-2.5-pro; ask a simple prompt → should succeed via fallback when pro is exhausted.
- Fault injection:
  - Temporarily deny access for pro on upstream to force fallback; confirm transparent success.

---

## Files/Touchpoints
- No change to aliases.
- Launcher: no change required if gateway binds 8317; optional small change if we choose an alternate upstream port for CLIProxyAPI.
- New component (gateway) added outside the repo or under .claude/tools/ (your preference).

## Next Steps
- Confirm Option A.
- I will draft the minimal gateway (Go or Python FastAPI) and a small systemd/launchd script to start it before the launcher runs.
- Add candidate list and timeouts to a small config file.
- Validate with the verification plan above.
