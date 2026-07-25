#!/usr/bin/env bash
# lean-ctx hook — rewrites shell commands
set -euo pipefail
LEAN_CTX_BIN="/Users/axos-agallentes/.cargo/bin/lean-ctx"
INPUT=$(cat)
CMD=$(echo "$INPUT" | grep -oE '"command":"([^"\\]|\\.)*"' | head -1 | sed 's/^"command":"//;s/"$//' | sed 's/\\"/"/g;s/\\\\/\\/g' 2>/dev/null || echo "")
if [ -z "$CMD" ] || echo "$CMD" | grep -qE "^(lean-ctx |\"?$LEAN_CTX_BIN\"? )"; then exit 0; fi
if printf '%s' "$CMD" | grep -qF '\n'; then exit 0; fi
case "$CMD" in
  git\ *|gh\ *|cargo\ *|npm\ *|pnpm\ *|yarn\ *|bun\ *|bunx\ *|deno\ *|vite\ *|python\ *|python3\ *|pip\ *|pip3\ *|uv\ *|pytest\ *|mypy\ *|ruff\ *|go\ *|golangci\-lint*|docker\ *|docker\-compose*|kubectl\ *|helm\ *|aws\ *|terraform\ *|tofu\ *|eslint\ *|prettier\ *|tsc\ *|biome\ *|curl\ *|wget\ *|php\ *|composer\ *|dotnet\ *|bundle\ *|rake\ *|mix\ *|swift\ *|zig\ *|cmake\ *|make\ *|grep\ *|egrep\ *|fgrep\ *|rg\ *|ls\ *|find\ *)
    SHELL_ESC=$(printf '%s' "$CMD" | sed 's/\\/\\\\/g;s/"/\\"/g')
    REWRITE="\"$LEAN_CTX_BIN\" -c \"$SHELL_ESC\""
    JSON_CMD=$(printf '%s' "$REWRITE" | sed 's/\\/\\\\/g;s/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","updatedInput":{"command":"%s"}}}' "$JSON_CMD" ;;
  *) exit 0 ;;
esac
