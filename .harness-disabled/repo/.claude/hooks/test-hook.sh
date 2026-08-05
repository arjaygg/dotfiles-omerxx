#!/usr/bin/env bash
# Hook test harness — pipe fixture JSON into a hook and report results.
#
# Usage:
#   test-hook.sh <hook-name> <fixture-name>
#   test-hook.sh --all                        # Run all fixtures for all hooks
#   test-hook.sh <hook-name> --all            # Run all fixtures for one hook
#
# Fixtures live in: ~/.dotfiles/.claude/hooks/fixtures/<hook-name>/<fixture-name>.json
# Each fixture file is a JSON object matching the hook's expected stdin format.
# Expected exit codes are encoded in the filename: <name>.exit<N>.json
#   e.g., grep-symbol.exit2.json → expects exit code 2
#   If no .exitN suffix, any exit code is accepted (report-only mode).
#
# Examples:
#   test-hook.sh serena-tool-priority grep-symbol.exit2
#   test-hook.sh bash-output-guard --all
#   test-hook.sh --all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="${SCRIPT_DIR}"
FIXTURES_DIR="${HOOKS_DIR}/fixtures"
PASS=0
FAIL=0
SKIP=0

run_fixture() {
    local hook_name="$1"
    local fixture_file="$2"
    local fixture_basename
    fixture_basename=$(basename "$fixture_file" .json)

    local hook_path="${HOOKS_DIR}/${hook_name}.sh"
    if [[ ! -x "$hook_path" ]]; then
        printf "  SKIP  %-40s (hook not found: %s)\n" "$fixture_basename" "$hook_path"
        ((SKIP++)) || true
        return
    fi

    # Extract expected exit code from filename (e.g., grep-symbol.exit2.json → 2)
    local expected_exit=""
    if [[ "$fixture_basename" =~ \.exit([0-9]+)$ ]]; then
        expected_exit="${BASH_REMATCH[1]}"
    fi

    # Run the hook
    local actual_exit=0
    local stderr_output
    stderr_output=$(bash "$hook_path" < "$fixture_file" 2>&1 >/dev/null) || actual_exit=$?

    # Report
    if [[ -n "$expected_exit" ]]; then
        if [[ "$actual_exit" -eq "$expected_exit" ]]; then
            printf "  PASS  %-40s (exit %s)\n" "$fixture_basename" "$actual_exit"
            ((PASS++)) || true
        else
            printf "  FAIL  %-40s (expected exit %s, got %s)\n" "$fixture_basename" "$expected_exit" "$actual_exit"
            [[ -n "$stderr_output" ]] && printf "        stderr: %s\n" "$stderr_output"
            ((FAIL++)) || true
        fi
    else
        printf "  INFO  %-40s (exit %s)\n" "$fixture_basename" "$actual_exit"
        [[ -n "$stderr_output" ]] && printf "        stderr: %s\n" "$stderr_output"
        ((SKIP++)) || true
    fi
}

run_hook_fixtures() {
    local hook_name="$1"
    local fixture_dir="${FIXTURES_DIR}/${hook_name}"
    if [[ ! -d "$fixture_dir" ]]; then
        echo "  No fixtures found at: $fixture_dir"
        return
    fi
    echo "── $hook_name ──"
    for f in "$fixture_dir"/*.json; do
        [[ -f "$f" ]] || continue
        run_fixture "$hook_name" "$f"
    done
}

# --- Main ---
if [[ "${1:-}" == "--all" ]]; then
    echo "Running all hook fixtures..."
    echo
    for d in "$FIXTURES_DIR"/*/; do
        [[ -d "$d" ]] || continue
        hook_name=$(basename "$d")
        run_hook_fixtures "$hook_name"
        echo
    done
elif [[ "${2:-}" == "--all" || -z "${2:-}" && -n "${1:-}" ]]; then
    hook_name="$1"
    if [[ "$hook_name" == "--all" ]]; then
        exec "$0" --all
    fi
    if [[ -z "${2:-}" ]]; then
        run_hook_fixtures "$hook_name"
    else
        run_hook_fixtures "$hook_name"
    fi
else
    hook_name="$1"
    fixture_name="$2"
    fixture_file="${FIXTURES_DIR}/${hook_name}/${fixture_name}.json"
    if [[ ! -f "$fixture_file" ]]; then
        echo "Fixture not found: $fixture_file" >&2
        exit 1
    fi
    run_fixture "$hook_name" "$fixture_file"
fi

echo
echo "Results: $PASS passed, $FAIL failed, $SKIP skipped"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
