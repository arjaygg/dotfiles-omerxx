#!/usr/bin/env bash
# PreToolUse: Warn when Grep/Glob/Read could use Serena equivalents
# Matcher: Grep|Glob|Read
# Exit: 0 = pass/warn, or JSON block via hook_block() when config is "block"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="serena-tool-priority"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)

# If enforcement is "off", skip all checks
[[ "$_EXIT_CODE" -eq 0 ]] && exit 0

# Fast path: skip if pctx is not configured (before reading stdin)
PCTX_CONFIG="${HOME}/.config/pctx/pctx.json"
[[ ! -f "$PCTX_CONFIG" ]] && exit 0

INPUT=$(cat)

IFS=$'\001' read -r TOOL_NAME FILE_PATH PATTERN LIMIT < <(
    echo "$INPUT" | jq -r '[.tool_name // "", .tool_input.file_path // .tool_input.path // "", .tool_input.pattern // "", (.tool_input.limit // "" | tostring)] | join("\u0001")' 2>/dev/null || printf '\001\001\001'
)

# --- Non-code file extensions: skip these ---
NON_CODE_EXT="md|json|yaml|yml|sql|txt|env|toml|csv|tsv|xml|html|css|lock|sum|mod|cfg|ini|conf|sh|bash|zsh"

is_non_code() {
    local path="$1"
    local ext="${path##*.}"
    ext="${ext,,}" # lowercase
    [[ "$ext" =~ ^($NON_CODE_EXT)$ ]]
}

# --- Grep: suggest Serena.findSymbol for symbol-like patterns ---
if [[ "$TOOL_NAME" == "Grep" && -n "$PATTERN" ]]; then
    # Symbol-like patterns: func/class/type/struct/interface followed by a name,
    # or a bare PascalCase/camelCase identifier (likely a symbol lookup)
    if [[ "$PATTERN" =~ ^(func|class|type|struct|interface|def|fn)[[:space:]]+[A-Za-z] ]]; then
        _msg="HINT: For symbol lookups, Serena.findSymbol is more precise than Grep and returns structural context."
        if [[ "$_EXIT_CODE" -eq 2 ]]; then
            hook_block "$_HOOK_NAME" "$TOOL_NAME" "$_msg"
        else
            echo "$_msg"
            hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true; exit 0
        fi
    fi
    # PascalCase identifier (e.g. "HandleRequest", "WorkerPool") — likely a symbol
    if [[ "$PATTERN" =~ ^[A-Z][a-zA-Z0-9]+$ ]]; then
        _msg="HINT: '$PATTERN' looks like a symbol name. Consider Serena.findSymbol('$PATTERN') for structural results."
        if [[ "$_EXIT_CODE" -eq 2 ]]; then
            hook_block "$_HOOK_NAME" "$TOOL_NAME" "$_msg"
        else
            echo "$_msg"
            hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true; exit 0
        fi
    fi
fi

# --- Read: suggest Serena.getSymbolsOverview for source code without limit ---
# Note: .go files are already handled by pre-tool-gate.sh — skip them here
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" && -z "$LIMIT" ]]; then
    if [[ "$FILE_PATH" == *.go ]]; then
        exit 0  # pre-tool-gate.sh handles this
    fi
    if ! is_non_code "$FILE_PATH" && [[ -f "$FILE_PATH" ]]; then
        _msg="HINT: Consider Serena.getSymbolsOverview for '$FILE_PATH' to see structure first, then Read with limit/offset for specific symbols."
        if [[ "$_EXIT_CODE" -eq 2 ]]; then
            hook_block "$_HOOK_NAME" "$TOOL_NAME" "$_msg"
        else
            echo "$_msg"
            hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true; exit 0
        fi
    fi
fi

# --- Glob: suggest Serena.findFile for targeted filename searches ---
if [[ "$TOOL_NAME" == "Glob" && -n "$PATTERN" ]]; then
    # Targeted search: pattern is a specific filename (not a broad wildcard sweep)
    # e.g. "**/worker.go" or "*/routes.go" — not "**/*.go" or "src/**"
    if [[ "$PATTERN" =~ /[a-zA-Z0-9_-]+\.[a-zA-Z]+$ && ! "$PATTERN" =~ \*\.[a-zA-Z]+$ && ! "$PATTERN" =~ ^\*\* ]]; then
        FILENAME="${PATTERN##*/}"
        echo "HINT: For finding '$FILENAME', Serena.findFile('$FILENAME') searches the project index and is often faster."
        hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true; exit 0
    fi
fi

hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true
exit 0
