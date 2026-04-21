#!/usr/bin/env bash
# Violation Pattern Analysis System
# Tracks where, when, and how hyper-atomic violations occur in practice
set -euo pipefail

VIOLATION_DB="${HOME}/.local/share/claude-hooks/violations.db"
VIOLATION_LOG="/tmp/.claude-violations-$(id -u).log"

# Ensure database exists
_ensure_violation_db() {
    local db_dir
    db_dir=$(dirname "$VIOLATION_DB")
    [[ -d "$db_dir" ]] || mkdir -p "$db_dir"
    
    sqlite3 "$VIOLATION_DB" <<'SQL'
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    session_id TEXT DEFAULT '',
    repo_path TEXT NOT NULL,
    violation_type TEXT NOT NULL,  -- 'level1_block', 'level4_block', 'level1_pass', 'git_operation'
    enforcement_level TEXT NOT NULL,  -- 'pre_tool_gate', 'pre_commit', 'none'
    atomic_state TEXT DEFAULT '',  -- 'in_progress', 'blocked', 'overgrown', 'ready_to_commit'
    operation_type TEXT DEFAULT '',  -- 'Edit', 'Write', 'Bash', 'git_add', 'git_commit'
    file_path TEXT DEFAULT '',
    staged_files INTEGER DEFAULT 0,
    subsystem_count INTEGER DEFAULT 0,
    diff_lines INTEGER DEFAULT 0,
    time_since_last_op INTEGER DEFAULT 0,  -- seconds since last operation
    violation_reason TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp);
CREATE INDEX IF NOT EXISTS idx_violations_session ON violations(session_id);

CREATE TABLE IF NOT EXISTS operation_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    session_id TEXT DEFAULT '',
    repo_path TEXT NOT NULL,
    operation_type TEXT NOT NULL,  -- 'edit', 'add', 'commit', 'status_check'
    file_path TEXT DEFAULT '',
    atomic_state_before TEXT DEFAULT '',
    atomic_state_after TEXT DEFAULT '',
    subsystems_before INTEGER DEFAULT 0,
    subsystems_after INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ops_session ON operation_sequence(session_id);
CREATE INDEX IF NOT EXISTS idx_ops_timestamp ON operation_sequence(timestamp);
SQL
}

# Fast logging function (append to file, batch to SQLite later)
log_violation() {
    local violation_type="$1"
    local enforcement_level="$2"
    local operation_type="$3"
    local file_path="${4:-}"
    local violation_reason="${5:-}"
    
    local session_id="${CLAUDE_SESSION_ID:-}"
    local repo_path
    repo_path=$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")
    local ts
    ts=$(date '+%Y-%m-%dT%H:%M:%S')
    
    # Get current atomic state
    local atomic_state
    atomic_state=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" 2>/dev/null || echo "unknown")
    
    # Get staged file metrics
    local staged_files=0
    local subsystem_count=0
    local diff_lines=0
    if [[ "$atomic_state" != "in_progress" && "$atomic_state" != "unknown" ]]; then
        local atomic_json
        atomic_json=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --json 2>/dev/null || echo '{}')
        staged_files=$(echo "$atomic_json" | jq -r '.staged_files // 0' 2>/dev/null || echo 0)
        subsystem_count=$(echo "$atomic_json" | jq -r '.subsystem_count // 0' 2>/dev/null || echo 0)
        diff_lines=$(echo "$atomic_json" | jq -r '.diff_lines // 0' 2>/dev/null || echo 0)
    fi
    
    # Calculate time since last operation
    local time_since_last=0
    local last_op_file="/tmp/.claude-last-operation-$(id -u)"
    if [[ -f "$last_op_file" ]]; then
        local last_ts
        last_ts=$(cat "$last_op_file" 2>/dev/null || echo 0)
        local current_ts
        current_ts=$(date '+%s')
        time_since_last=$(( current_ts - last_ts ))
    fi
    echo "$(date '+%s')" > "$last_op_file"
    
    # Log to file (batch to SQLite later)
    printf '%s|%s|%s|%s|%s|%s|%s|%s|%s|%d|%d|%d|%d|%s\n' \
        "$ts" "$session_id" "$repo_path" "$violation_type" "$enforcement_level" \
        "$atomic_state" "$operation_type" "$file_path" "$staged_files" \
        "$subsystem_count" "$diff_lines" "$time_since_last" "$violation_reason" \
        >> "$VIOLATION_LOG" 2>/dev/null || true
}

# Log operation sequence (for timing analysis)
log_operation() {
    local operation_type="$1"
    local file_path="${2:-}"
    
    local session_id="${CLAUDE_SESSION_ID:-}"
    local repo_path
    repo_path=$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")
    local ts
    ts=$(date '+%Y-%m-%dT%H:%M:%S')
    
    # Get atomic state before and after (for operations that change it)
    local state_before
    local state_after
    state_before=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" 2>/dev/null || echo "unknown")
    
    case "$operation_type" in
        edit|add)
            # For edits/adds, state might change
            sleep 0.1  # Brief delay to let filesystem settle
            state_after=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" 2>/dev/null || echo "unknown")
            ;;
        *)
            state_after="$state_before"
            ;;
    esac
    
    # Extract subsystem counts
    local subs_before=0
    local subs_after=0
    if [[ "$state_before" != "in_progress" && "$state_before" != "unknown" ]]; then
        subs_before=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --json 2>/dev/null | jq -r '.subsystem_count // 0' || echo 0)
    fi
    if [[ "$state_after" != "in_progress" && "$state_after" != "unknown" ]]; then
        subs_after=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --json 2>/dev/null | jq -r '.subsystem_count // 0' || echo 0)
    fi
    
    # Log sequence entry (fast file append)
    printf '%s|%s|%s|%s|%s|%s|%s|%d|%d\n' \
        "$ts" "$session_id" "$repo_path" "$operation_type" "$file_path" \
        "$state_before" "$state_after" "$subs_before" "$subs_after" \
        >> "/tmp/.claude-operations-$(id -u).log" 2>/dev/null || true
}

# Flush logs to SQLite (called periodically)
flush_violations() {
    _ensure_violation_db
    
    local violation_log="$VIOLATION_LOG"
    local operation_log="/tmp/.claude-operations-$(id -u).log"
    local count=0
    
    # Flush violations
    if [[ -f "$violation_log" ]]; then
        while IFS='|' read -r ts session_id repo_path violation_type enforcement_level \
                                 atomic_state operation_type file_path staged_files \
                                 subsystem_count diff_lines time_since_last violation_reason; do
            sqlite3 "$VIOLATION_DB" "INSERT INTO violations (timestamp, session_id, repo_path, violation_type, enforcement_level, atomic_state, operation_type, file_path, staged_files, subsystem_count, diff_lines, time_since_last_op, violation_reason) VALUES ('$ts', '$session_id', '$repo_path', '$violation_type', '$enforcement_level', '$atomic_state', '$operation_type', '$file_path', $staged_files, $subsystem_count, $diff_lines, $time_since_last, '$violation_reason');" 2>/dev/null || true
            ((count++)) || true
        done < "$violation_log"
        rm -f "$violation_log"
    fi
    
    # Flush operations
    if [[ -f "$operation_log" ]]; then
        while IFS='|' read -r ts session_id repo_path operation_type file_path \
                                 state_before state_after subs_before subs_after; do
            sqlite3 "$VIOLATION_DB" "INSERT INTO operation_sequence (timestamp, session_id, repo_path, operation_type, file_path, atomic_state_before, atomic_state_after, subsystems_before, subsystems_after) VALUES ('$ts', '$session_id', '$repo_path', '$operation_type', '$file_path', '$state_before', '$state_after', $subs_before, $subs_after);" 2>/dev/null || true
        done < "$operation_log"
        rm -f "$operation_log"
    fi
    
    echo "Flushed $count violation events to database."
}

# Analysis commands
cmd_violation_summary() {
    _ensure_violation_db
    echo "Violation Pattern Analysis (last 7 days)"
    echo "═══════════════════════════════════════════════════════════════"
    sqlite3 -header -column "$VIOLATION_DB" <<'SQL'
SELECT
    violation_type,
    enforcement_level,
    COUNT(*) as total,
    ROUND(AVG(time_since_last_op), 1) as avg_time_gap_sec,
    ROUND(AVG(subsystem_count), 1) as avg_subsystems
FROM violations
WHERE timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY violation_type, enforcement_level
ORDER BY total DESC;
SQL
}

cmd_timing_analysis() {
    _ensure_violation_db
    echo "Operation Timing Analysis (violations by time gap)"
    echo "═══════════════════════════════════════════════════════════════"
    sqlite3 -header -column "$VIOLATION_DB" <<'SQL'
SELECT
    CASE
        WHEN time_since_last_op < 5 THEN '<5s'
        WHEN time_since_last_op < 30 THEN '5-30s'
        WHEN time_since_last_op < 120 THEN '30s-2m'
        ELSE '>2m'
    END as time_gap,
    COUNT(*) as violations,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM violations WHERE timestamp >= datetime('now', '-7 days', 'localtime')), 1) as percentage
FROM violations
WHERE timestamp >= datetime('now', '-7 days', 'localtime')
    AND violation_type IN ('level1_block', 'level4_block')
GROUP BY 1
ORDER BY violations DESC;
SQL
}

cmd_coverage_gaps() {
    _ensure_violation_db
    echo "Coverage Gap Analysis (Level 1 vs Level 4)"
    echo "═══════════════════════════════════════════════════════════════"
    sqlite3 -header -column "$VIOLATION_DB" <<'SQL'
SELECT
    enforcement_level,
    operation_type,
    COUNT(*) as blocks,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM violations WHERE violation_type LIKE '%_block'), 1) as percentage_of_blocks
FROM violations
WHERE violation_type LIKE '%_block'
    AND timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY enforcement_level, operation_type
ORDER BY blocks DESC;
SQL
}

# Main CLI
case "${1:-summary}" in
    log)
        shift
        log_violation "$@"
        ;;
    log-op)
        shift
        log_operation "$@"
        ;;
    flush)
        flush_violations
        ;;
    summary)
        cmd_violation_summary
        ;;
    timing)
        cmd_timing_analysis
        ;;
    gaps)
        cmd_coverage_gaps
        ;;
    *)
        echo "Usage: violation-tracker.sh {log|log-op|flush|summary|timing|gaps}" >&2
        exit 1
        ;;
esac