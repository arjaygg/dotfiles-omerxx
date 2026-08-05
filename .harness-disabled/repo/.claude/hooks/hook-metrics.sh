#!/usr/bin/env bash
# Hook metrics — log and query hook execution data via SQLite.
#
# Usage:
#   As a library (source from hooks):
#     source "$HOME/.dotfiles/.claude/hooks/hook-metrics.sh"
#     hook_metric "serena-tool-priority" "Grep" 2  # hook_name, tool_name, exit_code
#
#   As a CLI (query metrics):
#     hook-metrics.sh summary              # Summary table by hook
#     hook-metrics.sh recent [N]           # Last N events (default 20)
#     hook-metrics.sh compliance           # Warn/block compliance rates
#     hook-metrics.sh reset                # Clear all metrics

set -euo pipefail

METRICS_DB="${HOME}/.local/share/claude-hooks/metrics.db"
HOOK_CONFIG="${HOME}/.dotfiles/.claude/hooks/hook-config.yaml"

# Read enforcement level for a hook: "warn" (default), "block", or "off"
hook_enforcement_level() {
    local hook_name="$1"
    local level="warn"  # default
    if [[ -f "$HOOK_CONFIG" ]]; then
        local val
        val=$(grep "^${hook_name}:" "$HOOK_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d '[:space:]')
        [[ -n "$val" ]] && level="$val"
    fi
    echo "$level"
}

# Map enforcement level to exit code.
# Per Claude Code docs: exit 2 = block (stderr shown to Claude); exit 1 = non-blocking (tool proceeds).
# "warn" is advisory-only: hint printed to stdout, tool is not halted.
#   block → 2  (actually blocks; Claude sees stderr as reason)
#   warn  → 0  (advisory only; stdout hint, tool proceeds)
#   off   → 0  (disabled)
hook_exit_code() {
    local level
    level=$(hook_enforcement_level "$1")
    case "$level" in
        block) echo 2 ;;
        off)   echo 0 ;;
        *)     echo 0 ;;
    esac
}

# Emit a JSON structured block decision and exit 0.
# Preferred over exit 2 + stderr: Claude always sees the reason regardless of
# deny-list interaction order.
# Usage: hook_block "hook-name" "tool-name" "Human-readable reason"
hook_block() {
    local hook_name="$1"
    local tool_name="$2"
    local reason="$3"
    hook_metric "$hook_name" "$tool_name" 2 2>/dev/null || true
    jq -n --arg reason "$reason" '{"decision":"block","reason":$reason}'
    exit 0
}

_DB_INITIALIZED=0

_ensure_db() {
    [[ "$_DB_INITIALIZED" -eq 1 && -f "$METRICS_DB" ]] && return 0
    local db_dir
    db_dir=$(dirname "$METRICS_DB")
    [[ -d "$db_dir" ]] || mkdir -p "$db_dir"
    sqlite3 "$METRICS_DB" <<'SQL'
CREATE TABLE IF NOT EXISTS hook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    hook_name TEXT NOT NULL,
    tool_name TEXT DEFAULT '',
    exit_code INTEGER NOT NULL,
    session_id TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_hook_events_hook ON hook_events(hook_name);
CREATE INDEX IF NOT EXISTS idx_hook_events_ts ON hook_events(timestamp);
CREATE TABLE IF NOT EXISTS learning_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    session_id TEXT NOT NULL,
    hook_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    blocked_tool TEXT DEFAULT '',
    recovery_tool TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_learning_events_hook ON learning_events(hook_name);
SQL
    # Idempotent column add — sqlite3 has no ADD COLUMN IF NOT EXISTS, so guard
    # with PRAGMA table_info rather than relying on `|| true` alone (set -e
    # would otherwise treat a real errors-elsewhere case as harmless too).
    if ! sqlite3 "$METRICS_DB" "PRAGMA table_info(hook_events);" 2>/dev/null | grep -q '|duration_ms|'; then
        sqlite3 "$METRICS_DB" "ALTER TABLE hook_events ADD COLUMN duration_ms INTEGER DEFAULT 0;" 2>/dev/null || true
    fi
    _DB_INITIALIZED=1
}

METRICS_LOG="/tmp/.claude-hook-metrics-$(id -u).log"

# Called from hooks to log a metric (fast — flat file append)
# duration_ms is optional (defaults to 0) — pass it from dispatchers timing
# sub-hook execution with `date +%s%N` before/after.
hook_metric() {
    local hook_name="${1:-unknown}"
    local tool_name="${2:-}"
    local exit_code="${3:-0}"
    local session_id="${4:-}"
    local duration_ms="${5:-0}"
    local ts
    ts=$(date '+%Y-%m-%dT%H:%M:%S')
    printf '%s|%s|%s|%s|%s|%s\n' "$ts" "$hook_name" "$tool_name" "$exit_code" "$session_id" "$duration_ms" >> "$METRICS_LOG" 2>/dev/null || true
}

# Record a learning event (behavioral classification) — direct SQLite write.
# Only call this off the PreToolUse hot path (e.g. PostToolUse, CLI). For
# PreToolUse gates, use hook_learning_metric() below instead.
hook_learning_event() {
    local session_id="${1:-}"
    local hook_name="${2:-unknown}"
    local event_type="${3:-}"  # preemptive, block_recover, warn_adapt, warn_ignore, block_repeat
    local blocked_tool="${4:-}"
    local recovery_tool="${5:-}"
    _ensure_db
    sqlite3 "$METRICS_DB" "INSERT INTO learning_events (session_id, hook_name, event_type, blocked_tool, recovery_tool) VALUES ('$session_id', '$hook_name', '$event_type', '$blocked_tool', '$recovery_tool');" 2>/dev/null || true
}

LEARNING_LOG="/tmp/.claude-hook-learning-$(id -u).log"

# Fast flat-file append for learning events — safe to call from PreToolUse
# gates (no SQLite I/O on the hot path). Drained into learning_events by
# cmd_flush(), same pattern as hook_metric()/METRICS_LOG.
hook_learning_metric() {
    local session_id="${1:-}"
    local hook_name="${2:-unknown}"
    local event_type="${3:-}"
    local blocked_tool="${4:-}"
    local recovery_tool="${5:-}"
    local ts
    ts=$(date '+%Y-%m-%dT%H:%M:%S')
    printf '%s|%s|%s|%s|%s|%s\n' "$ts" "$session_id" "$hook_name" "$event_type" "$blocked_tool" "$recovery_tool" >> "$LEARNING_LOG" 2>/dev/null || true
}

# --- CLI commands ---

cmd_summary() {
    _ensure_db
    echo "Hook Metrics Summary (last 7 days)"
    echo "═══════════════════════════════════════════════════════════════"
    sqlite3 -header -column "$METRICS_DB" <<'SQL'
SELECT
    hook_name AS hook,
    COUNT(*) AS total,
    SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) AS pass,
    SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) AS warn,
    SUM(CASE WHEN exit_code = 2 THEN 1 ELSE 0 END) AS block,
    ROUND(100.0 * SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pass_pct,
    ROUND(AVG(duration_ms), 1) AS avg_ms
FROM hook_events
WHERE timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY hook_name
ORDER BY total DESC;
SQL
}

cmd_recent() {
    local limit="${1:-20}"
    _ensure_db
    sqlite3 -header -column "$METRICS_DB" "
SELECT timestamp, hook_name, tool_name, exit_code
FROM hook_events
ORDER BY id DESC
LIMIT $limit;
"
}

cmd_compliance() {
    _ensure_db
    echo "Warning Compliance (warn events by hook, last 7 days)"
    echo "═══════════════════════════════════════════════════════"
    sqlite3 -header -column "$METRICS_DB" <<'SQL'
SELECT
    hook_name AS hook,
    SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) AS warnings,
    SUM(CASE WHEN exit_code = 2 THEN 1 ELSE 0 END) AS blocks,
    ROUND(100.0 * SUM(CASE WHEN exit_code IN (0,2) THEN 1 ELSE 0 END) / COUNT(*), 1) AS trigger_rate_pct
FROM hook_events
WHERE timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY hook_name
HAVING warnings > 0 OR blocks > 0
ORDER BY trigger_rate_pct DESC;
SQL
}

cmd_reset() {
    _ensure_db
    local count
    count=$(sqlite3 "$METRICS_DB" "SELECT COUNT(*) FROM hook_events;")
    sqlite3 "$METRICS_DB" "DELETE FROM hook_events;"
    sqlite3 "$METRICS_DB" "DELETE FROM learning_events;"
    rm -f "$METRICS_LOG" "$LEARNING_LOG"
    echo "Cleared $count metric events."
}

cmd_effectiveness() {
    _ensure_db
    echo "Hook Effectiveness Report (last 30 days)"
    echo "═══════════════════════════════════════════════════════════════"
    sqlite3 -header -column "$METRICS_DB" <<'SQL'
SELECT
    hook_name AS hook,
    COUNT(*) AS total,
    SUM(CASE WHEN event_type = 'preemptive' THEN 1 ELSE 0 END) AS preempt,
    SUM(CASE WHEN event_type = 'block_recover' THEN 1 ELSE 0 END) AS recover,
    SUM(CASE WHEN event_type = 'warn_adapt' THEN 1 ELSE 0 END) AS adapt,
    SUM(CASE WHEN event_type = 'warn_ignore' THEN 1 ELSE 0 END) AS ignore_ct,
    SUM(CASE WHEN event_type = 'block_repeat' THEN 1 ELSE 0 END) AS repeat_ct,
    ROUND(
        (2.0 * SUM(CASE WHEN event_type = 'preemptive' THEN 1 ELSE 0 END)
         + 1.0 * SUM(CASE WHEN event_type = 'block_recover' THEN 1 ELSE 0 END)
         + 1.0 * SUM(CASE WHEN event_type = 'warn_adapt' THEN 1 ELSE 0 END)
         - 1.0 * SUM(CASE WHEN event_type = 'warn_ignore' THEN 1 ELSE 0 END)
         - 2.0 * SUM(CASE WHEN event_type = 'block_repeat' THEN 1 ELSE 0 END)
        ) / NULLIF(COUNT(*), 0),
    2) AS LES
FROM learning_events
WHERE timestamp >= datetime('now', '-30 days', 'localtime')
GROUP BY hook_name
ORDER BY LES DESC;
SQL
}

cmd_flush() {
    _ensure_db
    local log_file="$METRICS_LOG"
    local count=0
    if [[ -f "$log_file" ]]; then
        while IFS='|' read -r ts hook_name tool_name exit_code session_id duration_ms; do
            duration_ms="${duration_ms:-0}"
            sqlite3 "$METRICS_DB" "INSERT INTO hook_events (timestamp, hook_name, tool_name, exit_code, session_id, duration_ms) VALUES ('$ts', '$hook_name', '$tool_name', $exit_code, '$session_id', $duration_ms);" 2>/dev/null || true
            ((count++)) || true
        done < "$log_file"
        rm -f "$log_file"
    fi
    echo "Flushed $count metric events to SQLite."

    local learn_count=0
    if [[ -f "$LEARNING_LOG" ]]; then
        while IFS='|' read -r ts session_id hook_name event_type blocked_tool recovery_tool; do
            sqlite3 "$METRICS_DB" "INSERT INTO learning_events (timestamp, session_id, hook_name, event_type, blocked_tool, recovery_tool) VALUES ('$ts', '$session_id', '$hook_name', '$event_type', '$blocked_tool', '$recovery_tool');" 2>/dev/null || true
            ((learn_count++)) || true
        done < "$LEARNING_LOG"
        rm -f "$LEARNING_LOG"
    fi
    echo "Flushed $learn_count learning events to SQLite."
}

# --- Main (CLI mode) ---
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    case "${1:-summary}" in
        summary)       cmd_summary ;;
        recent)        cmd_recent "${2:-20}" ;;
        compliance)    cmd_compliance ;;
        effectiveness) cmd_effectiveness ;;
        reset)         cmd_reset ;;
        flush)         cmd_flush ;;
        *)             echo "Usage: hook-metrics.sh {summary|recent [N]|compliance|effectiveness|reset|flush}" >&2; exit 1 ;;
    esac
fi
