#!/usr/bin/env bash
# Hook auto-graduation — promotes/demotes hooks based on Learning Effectiveness Score.
# Run at session start or daily via cron.
# Usage: bash .claude/hooks/hook-graduate.sh [--dry-run]
#
# Graduation ladder: BLOCK -> WARN -> OFF (instruction-only) -> GRADUATED
# Regression: if target metric regresses, re-enable at previous level.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true

STATE_FILE="${SCRIPT_DIR}/hook-graduation-state.json"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ ! -f "$STATE_FILE" ]]; then
    echo "No graduation state file found at $STATE_FILE"
    exit 1
fi

_ensure_db

echo "Hook Graduation Check"
echo "======================================================="
echo ""

# Read each hook's graduation config
for hook_name in $(jq -r '.hooks | keys[]' "$STATE_FILE"); do
    current_level=$(jq -r ".hooks[\"$hook_name\"].current_level" "$STATE_FILE")
    target_level=$(jq -r ".hooks[\"$hook_name\"].next_graduation.target_level" "$STATE_FILE")
    les_min=$(jq -r ".hooks[\"$hook_name\"].next_graduation.les_min" "$STATE_FILE")
    days_required=$(jq -r ".hooks[\"$hook_name\"].next_graduation.days_required" "$STATE_FILE")

    # Query LES from learning_events (last N days)
    les=$(sqlite3 "$METRICS_DB" "
        SELECT COALESCE(ROUND(
            (2.0 * SUM(CASE WHEN event_type = 'preemptive' THEN 1 ELSE 0 END)
             + 1.0 * SUM(CASE WHEN event_type = 'block_recover' THEN 1 ELSE 0 END)
             + 1.0 * SUM(CASE WHEN event_type = 'warn_adapt' THEN 1 ELSE 0 END)
             - 1.0 * SUM(CASE WHEN event_type = 'warn_ignore' THEN 1 ELSE 0 END)
             - 2.0 * SUM(CASE WHEN event_type = 'block_repeat' THEN 1 ELSE 0 END)
            ) / NULLIF(COUNT(*), 0), 2), 0.0)
        FROM learning_events
        WHERE hook_name = '$hook_name'
          AND timestamp >= datetime('now', '-${days_required} days', 'localtime');
    " 2>/dev/null || echo "0.0")

    event_count=$(sqlite3 "$METRICS_DB" "
        SELECT COUNT(*) FROM learning_events
        WHERE hook_name = '$hook_name'
          AND timestamp >= datetime('now', '-${days_required} days', 'localtime');
    " 2>/dev/null || echo "0")

    printf "  %-25s level=%-5s LES=%-6s events=%-4s target=%-5s " \
        "$hook_name" "$current_level" "$les" "$event_count" "$target_level"

    # Check graduation criteria
    min_events=10  # Need at least 10 events for a meaningful LES
    if [[ "$event_count" -lt "$min_events" ]]; then
        printf "(insufficient data)\n"
        continue
    fi

    # Compare LES to minimum (using bc for float comparison)
    qualifies=$(echo "$les >= $les_min" | bc -l 2>/dev/null || echo 0)

    if [[ "$qualifies" -eq 1 ]]; then
        printf "-> GRADUATE to $target_level"
        if [[ "$DRY_RUN" -eq 1 ]]; then
            printf " (dry-run)\n"
        else
            # Update hook-config.yaml
            sed -i '' "s/^${hook_name}: ${current_level}/${hook_name}: ${target_level}/" "${SCRIPT_DIR}/hook-config.yaml" 2>/dev/null || true
            # Update graduation state
            jq ".hooks[\"$hook_name\"].current_level = \"$target_level\" | .hooks[\"$hook_name\"].graduated_from = \"$current_level\" | .hooks[\"$hook_name\"].graduated_date = \"$(date '+%Y-%m-%d')\"" "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
            printf " done\n"
        fi
    else
        printf "(not ready: LES $les < $les_min)\n"
    fi
done

echo ""
echo "Done. Run with --dry-run to preview without changes."
