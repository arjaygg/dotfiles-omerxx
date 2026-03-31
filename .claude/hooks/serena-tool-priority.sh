#!/usr/bin/env bash
# PreToolUse: Warn when Grep/Glob/Read could use Serena equivalents
# Matcher: Grep|Glob|Read
# Exit: 0 = pass, 2 = warn (never blocks)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="serena-tool-priority"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)

# If enforcement is "off", skip all checks
[[ "$_EXIT_CODE" -eq 0 ]] && exit 0

INPUT=$(cat)

IFS=$'\001' read -r TOOL_NAME FILE_PATH PATTERN LIMIT < <(
    echo "$INPUT" | python3 -c "
import sys, json
SEP = '\x01'
try:
    d = json.load(sys.stdin)
    tool_name = d.get('tool_name', '')
    ti = d.get('tool_input', {})
    file_path = ti.get('file_path', ti.get('path', ''))
    pattern = ti.get('pattern', '')
    limit = str(ti.get('limit', ''))
    print(SEP.join([tool_name, file_path, pattern, limit]))
except:
    print(SEP * 3)
" 2>/dev/null || printf '\001\001\001'
)

# --- Skip if pctx is not configured ---
PCTX_CONFIG="${HOME}/.config/pctx/pctx.json"
if [[ ! -f "$PCTX_CONFIG" ]]; then
    exit 0
fi

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
        echo "HINT: For symbol lookups, Serena.findSymbol is more precise than Grep and returns structural context."
        hook_metric "$_HOOK_NAME" "$TOOL_NAME" "$_EXIT_CODE" 2>/dev/null || true; exit "$_EXIT_CODE"
    fi
    # PascalCase identifier (e.g. "HandleRequest", "WorkerPool") — likely a symbol
    if [[ "$PATTERN" =~ ^[A-Z][a-zA-Z0-9]+$ ]]; then
        echo "HINT: '$PATTERN' looks like a symbol name. Consider Serena.findSymbol('$PATTERN') for structural results."
        hook_metric "$_HOOK_NAME" "$TOOL_NAME" "$_EXIT_CODE" 2>/dev/null || true; exit "$_EXIT_CODE"
    fi
fi

# --- Read: suggest Serena.getSymbolsOverview for source code without limit ---
# Note: .go files are already handled by pre-tool-gate.sh — skip them here
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" && -z "$LIMIT" ]]; then
    if [[ "$FILE_PATH" == *.go ]]; then
        exit 0  # pre-tool-gate.sh handles this
    fi
    if ! is_non_code "$FILE_PATH" && [[ -f "$FILE_PATH" ]]; then
        echo "HINT: Consider Serena.getSymbolsOverview for '$FILE_PATH' to see structure first, then Read with limit/offset for specific symbols."
        hook_metric "$_HOOK_NAME" "$TOOL_NAME" "$_EXIT_CODE" 2>/dev/null || true; exit "$_EXIT_CODE"
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
