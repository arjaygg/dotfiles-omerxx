#!/usr/bin/env bash
# supermemory-project-check.sh — SessionStart hook
# Advises users to configure supermemory when .claude/.supermemory-claude/config.json is absent.
# Fires at most once per session via /tmp flag file.
# Always exits 0 — must never block session start.

set -uo pipefail

trap 'exit 0' ERR

emit_advisory() {
    local msg="$1"
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}' \
        "$(printf '%s' "$msg" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read())[1:-1])")"
}

main() {
    # 1. Detect git root; exit silently if not a git repo
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$REPO_ROOT" ]]; then
        exit 0
    fi

    # 2. Compute per-repo flag file path (md5 of git root path)
    REPO_HASH="$(printf '%s' "$REPO_ROOT" | md5 -q 2>/dev/null || printf '%s' "$REPO_ROOT" | md5sum | awk '{print $1}')"
    FLAG_FILE="/tmp/sm-checked-${REPO_HASH}"

    # 3. Skip if already ran this session
    if [[ -f "$FLAG_FILE" ]]; then
        exit 0
    fi

    # 4. Skip if config already exists (user has configured supermemory)
    CONFIG_PATH="${REPO_ROOT}/.claude/.supermemory-claude/config.json"
    if [[ -f "$CONFIG_PATH" ]]; then
        exit 0
    fi

    # 5. Write flag BEFORE emitting advisory (idempotent guard)
    touch "$FLAG_FILE" || true

    # 6. Emit advisory
    local advisory_msg
    advisory_msg="[SUPERMEMORY] This project has no memory config (.claude/.supermemory-claude/config.json missing). Run /project-config to set repoContainerTag, then /supermemory to index the codebase. This message shows once per session until configured."

    emit_advisory "$advisory_msg"
}

main
