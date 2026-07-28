#!/usr/bin/env bash
# Portable lean-ctx observe hook wrapper.
#
# Keep .claude/settings.json free of machine-specific lean-ctx install paths.
# Observation is telemetry only, so missing or failing lean-ctx must never break
# Claude Code hook events.

set -uo pipefail

INPUT=$(cat || true)

resolve_lean_ctx() {
    local candidate
    for candidate in \
        "$HOME/.local/bin/lean-ctx" \
        "$(command -v lean-ctx 2>/dev/null || true)" \
        "$HOME/.cargo/bin/lean-ctx"
    do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

LEAN_CTX_BIN=$(resolve_lean_ctx || true)
if [[ -z "$LEAN_CTX_BIN" ]]; then
    exit 0
fi

printf '%s' "$INPUT" | "$LEAN_CTX_BIN" hook observe >/dev/null 2>&1 || true
exit 0
