# 0016 — Untrack `.claude/settings.json`; generator bootstraps the runtime projection

**Status:** Accepted
**Date:** 2026-08-01
**Amends:** `0012-cross-client-config-portability.md` — its Step-7 scope-out ("any live runtime
write is intentionally, permanently out of scope") is lifted for one narrow case: an explicit,
operator-invoked bootstrap write of a *missing* runtime file.

## Context

`.claude/settings.json` was a tracked file simultaneously rewritten by three writers with three
different canonical forms:

1. The lean-ctx daemon, which rewrites its three hook commands to the absolute binary path
   (`/Users/<user>/.cargo/bin/lean-ctx`) — no configuration knob for `$HOME`-relative emission.
2. The Claude Code runtime, which re-sorts keys alphabetically and re-persists
   `skipDangerousModePermissionPrompt` whenever the user consents in the UI.
3. The `sanitize-staged-settings` pre-commit hook, which strips both back to the portable form
   required by the portability invariant.

The result was a perpetual dirty file and a red/green test treadmill: every commit of the
"canonical churned form" was immediately re-dirtied by the daemon/runtime, and sanitizing the
tests only moved the noise into `git status`.

## Decision

1. `.claude/settings.json` is **untracked and gitignored** — a runtime-managed projection, not
   distribution. Source of truth is `ai/config/claude/settings.base.json` (+ optional machine
   overlay `~/.config/dotfiles-ai/claude.overlay.json`), matching the 0011/0012 pattern already
   used by every other client.
2. `scripts/config_generate.py` gains an explicit `--write PATH` flag (atomic temp-file +
   `os.replace`, mode 600, strict portability validation). It runs **only** from `setup.sh` when
   the runtime file is absent (fresh-machine bootstrap). It never auto-runs against an existing
   live file — after bootstrap the runtime (daemon + Claude Code) owns the file.
3. `setup.sh` explicitly symlinks `~/.claude/settings.json` → the repo file (stow no longer sees
   it), and the boundary test now asserts the file is untracked+ignored plus parseable JSON
   (base-vs-live equality was dropped: runtime divergence such as `model` choice or
   `skipDangerousModePermissionPrompt` is legitimate state, not drift). The base template keeps
   the hygiene and dangerous-mode guarantees.

## Consequences

- The perpetual churn stops: daemon/runtime rewrites touch an untracked file; the portability
  invariant stays enforced on the tracked base template.
- Fresh machines get a working settings file from `setup.sh`; the lean-ctx daemon canonicalizes
  hook paths to absolute form on first run, as it already does today.
- `config_doctor.py`, `hook_target_check.py`, and `hook_config_check.py` keep working against the
  live file when present; `setup.sh --check` skips them when it is absent.
- The dangerous-mode-bypass guarantee stays scoped to the base template: fresh machines never
  inherit `skipDangerousModePermissionPrompt`.
