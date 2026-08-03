# 0022 — In-repo adapters and installed-file templates are separate files

**Status:** Accepted
**Date:** 2026-08-03
**Fixes:** two test regressions introduced by `98241a5` and `a549a02` (both already pushed to
`origin/main`)
**Amends:** `decisions/0020-user-global-instruction-durability.md`

## Decision

Split the two roles that `98241a5` conflated:

- **`.codex/AGENTS.md`** stays an **in-repo adapter** with repo-relative `@../ai/rules/…` imports,
  as asserted by `scripts/guidance_adapter_check.py`'s `REQUIRED_TEXT` table. Restored, plus the
  delegation rule.
- **`ai/config/codex/AGENTS.global.base.md`** (moved) is the **template for the live
  `~/.codex/AGENTS.md`**, using `@rules/…` paths that resolve in the installed location. `setup.sh`
  bootstraps from here; `config-integrity.sh`'s drift check points here.

Also: `model_provider = "headroom"` removed from the tracked `.codex/config.toml`. The `model` and
`model_reasoning_effort` values stay.

## Why

Two tests failed on pushed `main`, both from commits made earlier the same day:

1. **`test_guidance_adapter_check.py::test_current_repo_guidance_adapters_pass`** — `98241a5`
   rewrote `.codex/AGENTS.md`'s imports from `@../ai/rules/…` to `@rules/…` in order to make it a
   faithful copy of the live file. But `scripts/guidance_adapter_check.py` asserts every client
   adapter — Claude, Gemini, Codex, Cursor — carries repo-relative imports. Rule
   `codex-imports-context-compaction` went from 1 match to 0.

   The two roles are genuinely incompatible in one file: an in-repo adapter needs paths resolving
   inside the repo, a template needs paths resolving in `~/.codex/`. Two files is the only correct
   answer, and `hooks.global.base.json` from 0020 had already set that precedent — I simply failed
   to follow it for `AGENTS.md`.

2. **`test_headroom_hardening.py::test_project_codex_config_keeps_provider_settings_user_scoped`** —
   `a549a02` copied `model_provider = "headroom"` from the live config into the tracked one while
   fixing the coordinator-tier drift. That test asserts `model_provider`, `model_providers`, and the
   `headroom` MCP server are **absent** from the tracked file: the proxy is machine-local user scope,
   deliberately untracked. Copying a live value wholesale ignored a distinction the test exists to
   protect. The coordinator-tier half of that commit was correct and is kept.

Both were avoidable. I ran `config-integrity.sh` and `hook-integration-test.sh` before pushing but
never `pytest scripts/`, which is where the repo's real invariants live — and `hook-integration-test.sh`
had skipped all five of its cases on an auth failure, so the green signal it returned was empty.

## Alternatives rejected

- **Relax `guidance_adapter_check.py` to accept `@rules/…`:** rejected — it would weaken a checked
  invariant to accommodate a mistake, and the in-repo imports genuinely need to resolve in-repo.
- **Keep `.codex/AGENTS.md` as the template and drop it from the checker's table:** rejected — same
  objection, and it would leave Codex the only client without an adapter contract.
- **Leave `model_provider` tracked and amend the test:** rejected — the test encodes a real
  separation (machine-local proxy vs shared config). The value belongs only in the live file.
- **Revert `98241a5` and `a549a02` entirely:** rejected — each carried a genuine fix (the adapter
  role-claim collision; the coordinator-tier drift that would have silently demoted Codex to
  `gpt-5.5` on a rebuild). Only the overreaching parts are undone.

## Consequences

- Three Codex instruction artifacts now exist with distinct roles, which is more surface to keep
  straight: `AGENTS.md` at the repo root (project guidance), `.codex/AGENTS.md` (in-repo adapter),
  and `ai/config/codex/AGENTS.global.base.md` (live-file template). Each names the others.
- `pytest scripts/` must be run before pushing anything touching `.codex/`, `.claude/`, adapters, or
  config templates. `config-integrity.sh` does not cover these invariants and never did.
- **`pytest scripts/` fails 9 cases in a `.trees/` worktree that pass on the main working tree** —
  `test_read_before_overwrite_gate.py`. Verified independent of both this change and the pending
  hook edits: the failures reproduce in the worktree with either version of
  `pre-tool-gate-v2.sh`, so the cause is the worktree environment, not the hook. Pre-existing and
  not addressed here, but it means worktree test runs cannot be read at face value — a real trap for
  the stack workflow this repo mandates.

## Related

- `scripts/guidance_adapter_check.py`, `scripts/test_headroom_hardening.py`.
- `decisions/0016`, `decisions/0018`, `decisions/0020`, `decisions/0021`.
