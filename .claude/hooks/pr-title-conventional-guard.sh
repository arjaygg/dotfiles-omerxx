#!/usr/bin/env bash
# PreToolUse hook: enforce conventional PR titles for direct gh PR commands.
# - Non-matching commands: exit 0 (no-op)
# - Matching invalid commands: exit 1 (block)

set -euo pipefail
trap 'exit 0' ERR

INPUT="$(cat 2>/dev/null || echo "{}")"
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")"
CMD="$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"

[[ "$TOOL_NAME" == "Bash" ]] || exit 0

if [[ ! "$CMD" =~ ^[[:space:]]*gh[[:space:]]+pr[[:space:]]+(create|edit)([[:space:]]|$) ]]; then
    exit 0
fi

ACTION="${BASH_REMATCH[1]}"
TITLE=""

# Extract --title/-t from common quoted forms.
if [[ "$CMD" =~ (--title|-t)[[:space:]]+\"([^\"]+)\" ]]; then
    TITLE="${BASH_REMATCH[2]}"
elif [[ "$CMD" =~ (--title|-t)[[:space:]]+\'([^\']+)\' ]]; then
    TITLE="${BASH_REMATCH[2]}"
elif [[ "$CMD" =~ (--title|-t)[[:space:]]+([^[:space:]]+) ]]; then
    TITLE="${BASH_REMATCH[2]}"
fi

# Deterministic behavior: require title on create (so lint is predictable).
if [[ "$ACTION" == "create" && -z "$TITLE" ]]; then
    echo "BLOCKED: gh pr create requires --title in Conventional Commits format." >&2
    echo "Use: gh pr create --title \"feat: <summary>\" ..." >&2
    echo "Or use: ~/.dotfiles/.claude/scripts/stack pr <branch> <target> \"feat: <summary>\"" >&2
    exit 1
fi

# For edit, only validate when --title is explicitly present.
if [[ -n "$TITLE" ]]; then
    VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
    if [[ -f "$VALIDATOR" ]]; then
        # shellcheck disable=SC1090
        source "$VALIDATOR"
        if ! is_conventional_pr_title "$TITLE"; then
            echo "BLOCKED: PR title is not Conventional Commits compliant: \"$TITLE\"" >&2
            echo "Expected: <type>(optional-scope): <summary>" >&2
            echo "Allowed types: feat, fix, perf, refactor, test, ci, chore, docs, style, revert" >&2
            exit 1
        fi
    fi
fi

exit 0
