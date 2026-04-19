# Codex Hook Starter (Native + Compatibility Layer)

This directory now contains a Codex-native starter profile:

- `hooks.json` — Codex lifecycle hook wiring
- `hooks/*.sh` — compatibility wrappers
- `rules/default.rules` — shell approval guardrails

## What this does

- Enables a portable baseline across Claude and Codex.
- Preserves Claude-native advanced checks in `.claude/hooks/*`.
- Uses Codex-native hooks/rules where available.

## Setup

1. Ensure `.codex/config.toml` has:
   - `[features] codex_hooks = true`
2. Ensure this repo is stowed/symlinked into `~/.codex`.
3. Restart Codex after changing `hooks.json` or `.rules` files.

## Important limitations

- Codex `PreToolUse`/`PostToolUse` coverage is currently strongest for Bash-like tools.
- Do not rely on hooks alone for critical enforcement.
- Keep mandatory controls in CI as final gate.
