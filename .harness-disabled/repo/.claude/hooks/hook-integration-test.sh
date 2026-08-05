#!/usr/bin/env bash
# Hook integration tests — validates that hooks change Claude's behavior, not just fire correctly.
# Usage: bash .claude/hooks/hook-integration-test.sh [scenario_name]
# Requires: claude CLI with -p flag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="/tmp/hook-integration-tests-$(date '+%Y%m%d-%H%M%S')"
mkdir -p "$RESULTS_DIR"

PASS=0
FAIL=0
SKIP=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

run_scenario() {
    local name="$1"
    local prompt="$2"
    local check_fn="$3"
    local transcript="$RESULTS_DIR/${name}.jsonl"

    printf "  %-40s " "$name"

    # Run headless Claude with the prompt, capture transcript
    if ! claude -p "$prompt" --output-format jsonl > "$transcript" 2>/dev/null; then
        printf "${YELLOW}SKIP${NC} (claude -p failed)\n"
        ((SKIP++)) || true
        return
    fi

    # Run the check function against the transcript
    if $check_fn "$transcript"; then
        printf "${GREEN}PASS${NC}\n"
        ((PASS++)) || true
    else
        printf "${RED}FAIL${NC}\n"
        ((FAIL++)) || true
    fi
}

# --- Check functions ---

check_no_bash_cat() {
    local transcript="$1"
    # Pass if no Bash tool call contains "cat " in the command
    ! jq -r 'select(.type == "tool_use" and .tool_name == "Bash") | .tool_input.command // ""' "$transcript" 2>/dev/null | grep -q '^cat '
}

check_no_bash_grep() {
    local transcript="$1"
    ! jq -r 'select(.type == "tool_use" and .tool_name == "Bash") | .tool_input.command // ""' "$transcript" 2>/dev/null | grep -qE '^(grep |grep -)'
}

check_no_bash_find_ls() {
    local transcript="$1"
    ! jq -r 'select(.type == "tool_use" and .tool_name == "Bash") | .tool_input.command // ""' "$transcript" 2>/dev/null | grep -qE '^(find [./]|ls )'
}

check_read_before_edit() {
    local transcript="$1"
    # Extract tool sequence, check that Read appears before Edit for the same file
    local edit_file
    edit_file=$(jq -r 'select(.type == "tool_use" and .tool_name == "Edit") | .tool_input.file_path // ""' "$transcript" 2>/dev/null | head -1)
    [[ -z "$edit_file" ]] && return 0  # No edit = pass
    # Check if Read was called with this file before the Edit
    jq -r 'select(.type == "tool_use") | "\(.tool_name) \(.tool_input.file_path // "")"' "$transcript" 2>/dev/null | grep -q "^Read.*$edit_file"
}

check_uses_grep_tool() {
    local transcript="$1"
    # Pass if Grep tool (not Bash grep) was used
    jq -r 'select(.type == "tool_use") | .tool_name' "$transcript" 2>/dev/null | grep -q '^Grep$'
}

check_uses_glob_tool() {
    local transcript="$1"
    jq -r 'select(.type == "tool_use") | .tool_name' "$transcript" 2>/dev/null | grep -q '^Glob$'
}

# --- Scenarios ---

echo "Hook Integration Tests"
echo "═══════════════════════════════════════════════════"
echo ""

run_scenario "cat-blocked-uses-read" \
    "Show me the contents of CLAUDE.md" \
    check_no_bash_cat

run_scenario "grep-blocked-uses-grep-tool" \
    "Find all TODO comments in the codebase" \
    check_no_bash_grep

run_scenario "find-ls-blocked-uses-glob" \
    "List all shell scripts in the .claude/hooks directory" \
    check_no_bash_find_ls

run_scenario "read-before-edit" \
    "Add a comment to the top of .claude/hooks/hook-config.yaml saying '# tested'" \
    check_read_before_edit

run_scenario "uses-grep-tool-for-search" \
    "Search for 'hook_block' across the codebase" \
    check_uses_grep_tool

# --- Summary ---
echo ""
echo "═══════════════════════════════════════════════════"
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${SKIP} skipped${NC}"
echo "Transcripts: $RESULTS_DIR"

[[ "$FAIL" -eq 0 ]]
