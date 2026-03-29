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

_ensure_db() {
    local db_dir
    db_dir=$(dirname "$METRICS_DB")
    [[ -d "$db_dir" ]] || mkdir -p "$db_dir"
    if [[ ! -f "$METRICS_DB" ]]; then
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
SQL
    fi
}

# Called from hooks to log a metric (fast — single INSERT)
hook_metric() {
    local hook_name="${1:-unknown}"
    local tool_name="${2:-}"
    local exit_code="${3:-0}"
    local session_id="${4:-}"
    _ensure_db
    sqlite3 "$METRICS_DB" "INSERT INTO hook_events (hook_name, tool_name, exit_code, session_id) VALUES ('$hook_name', '$tool_name', $exit_code, '$session_id');" 2>/dev/null || true
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
    SUM(CASE WHEN exit_code = 2 THEN 1 ELSE 0 END) AS warn,
    SUM(CASE WHEN exit_code = 1 THEN 1 ELSE 0 END) AS block,
    ROUND(100.0 * SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pass_pct
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
    SUM(CASE WHEN exit_code = 2 THEN 1 ELSE 0 END) AS warnings,
    SUM(CASE WHEN exit_code = 1 THEN 1 ELSE 0 END) AS blocks,
    ROUND(100.0 * SUM(CASE WHEN exit_code IN (1,2) THEN 1 ELSE 0 END) / COUNT(*), 1) AS trigger_rate_pct
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
    echo "Cleared $count metric events."
}

# --- Main (CLI mode) ---
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    case "${1:-summary}" in
        summary)    cmd_summary ;;
        recent)     cmd_recent "${2:-20}" ;;
        compliance) cmd_compliance ;;
        reset)      cmd_reset ;;
        *)          echo "Usage: hook-metrics.sh {summary|recent [N]|compliance|reset}" >&2; exit 1 ;;
    esac
fi
