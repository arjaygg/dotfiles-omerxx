#!/usr/bin/env bash
# Checks for stale Claude Code memory entries (files not modified in N days).
# Run manually or via cron: stale-memory-check.sh [--days N] [--project PATH]
#
# Scans all MEMORY.md index files under ~/.claude/projects/ and flags
# memory files older than threshold.

set -euo pipefail

STALE_DAYS=30
PROJECT_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days) STALE_DAYS="$2"; shift 2 ;;
        --project) PROJECT_PATH="$2"; shift 2 ;;
        *) echo "Usage: stale-memory-check.sh [--days N] [--project PATH]" >&2; exit 1 ;;
    esac
done

STALE_COUNT=0
TOTAL_COUNT=0

check_memory_dir() {
    local memory_dir="$1"
    local memory_index="${memory_dir}/MEMORY.md"

    [[ -f "$memory_index" ]] || return

    local dir_name
    dir_name=$(dirname "$memory_dir")
    echo "── $(basename "$dir_name") ──"

    for f in "$memory_dir"/*.md; do
        [[ -f "$f" ]] || continue
        [[ "$(basename "$f")" == "MEMORY.md" ]] && continue

        ((TOTAL_COUNT++)) || true
        local basename_f
        basename_f=$(basename "$f")

        # Get file modification time
        local mod_epoch
        mod_epoch=$(stat -f%m "$f" 2>/dev/null || stat -c%Y "$f" 2>/dev/null || echo 0)
        local now_epoch
        now_epoch=$(date '+%s')
        local age_days=$(( (now_epoch - mod_epoch) / 86400 ))

        if [[ "$age_days" -ge "$STALE_DAYS" ]]; then
            ((STALE_COUNT++)) || true
            printf "  STALE  %-40s (%d days old)\n" "$basename_f" "$age_days"
        else
            printf "  OK     %-40s (%d days old)\n" "$basename_f" "$age_days"
        fi
    done
    echo
}

if [[ -n "$PROJECT_PATH" ]]; then
    # Check single project
    if [[ -d "$PROJECT_PATH/memory" ]]; then
        check_memory_dir "$PROJECT_PATH/memory"
    else
        echo "No memory directory found at: $PROJECT_PATH/memory" >&2
        exit 1
    fi
else
    # Check all projects
    for memory_md in "$HOME"/.claude/projects/*/memory/MEMORY.md; do
        [[ -f "$memory_md" ]] || continue
        check_memory_dir "$(dirname "$memory_md")"
    done
fi

echo "Summary: $TOTAL_COUNT memories checked, $STALE_COUNT stale (>$STALE_DAYS days)"
[[ "$STALE_COUNT" -eq 0 ]] && echo "All memories are current." || echo "Review stale memories — they may reference renamed files, removed functions, or outdated decisions."
