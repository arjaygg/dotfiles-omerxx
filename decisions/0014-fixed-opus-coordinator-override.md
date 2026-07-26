# 0014 — Fixed Opus coordinator overrides opusplan default (explicit user choice)

**Status:** Accepted
**Date:** 2026-07-26
**Supersedes (partially):** `decisions/0013-deterministic-model-routing-enforcement.md`

## Decision

Per explicit user request this session, `.claude/settings.json` (and its mirrored
`ai/config/claude/settings.base.json`) now sets:

- `"model": "opus"` (was `"opusplan"`)
- `"effortLevel": "low"` (was `"high"`)
- `"advisorModel": "fable"` (unchanged, already correct)

`ai/agents/cicd-audit.md`, `ai/agents/cicd-monitor.md`, `ai/agents/cicd-review.md` now set
`model: sonnet` (was `model: inherit`, backfilled by 0013). These three agents perform
non-trivial audit/monitoring/escalation reasoning — "others" tier per the user's routing
request — and `inherit` would silently escalate them to Opus now that the main-loop model is
fixed rather than plan-mode-conditional. `ai/agents/mcp_config_manager.md` already carries
`model: sonnet` from 0013 and is untouched.

## Why

The user explicitly asked for a fixed routing scheme: Opus as primary coordinator at low
effort, Fable as advisor, Sonnet as the default subagent tier, Haiku reserved for
trivial/mechanical work. This is a deliberate, stated override of the `opusplan` default that
0013 restored — not a rediscovery of the same accidental drift 0013 fixed. Recording it here so
a future session (or `config-integrity.sh`/test run) doesn't mistake this for undocumented drift
and "fix" it back to `opusplan`/`inherit`.

## Consequences

- Main-loop tier selection stays a manual, unenforceable setting (per 0013's documented gap) —
  this file records *why* the manual value is `opus` rather than `opusplan`, not a mechanism
  change.
- `check_agent_models()`'s enum (`{haiku, sonnet, opus, fable, inherit}`) still accepts `sonnet`
  here; no hook/test change required. `test_phase0_boundary.py`'s base-template byte-equality
  check requires `ai/config/claude/settings.base.json` to mirror `.claude/settings.json` exactly
  — confirmed via `cp` and a passing `pytest scripts/test_phase0_boundary.py -q` run.
- If the user's routing preference changes again, update this file rather than leaving the
  reasoning only in chat history.

## Alternatives rejected

- **Leave `opusplan`/`inherit` from 0013 in place:** rejected — contradicts the user's explicit,
  unambiguous request for a fixed Opus coordinator and Sonnet-tier CI/CD agents.
- **Silently override without a decision record:** rejected — indistinguishable from the
  unintentional `sonnet`-vs-`opusplan` drift 0013 exists to prevent; a future automated or manual
  "fix" could revert it without realizing it was deliberate.
