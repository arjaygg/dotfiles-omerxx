#!/usr/bin/env bash
# Violation Pattern Analysis Tools
# Generates comprehensive reports from violation tracking data
set -euo pipefail

TRACKER="$HOME/.dotfiles/.claude/hooks/violation-tracker.sh"

generate_report() {
    echo "🔍 Hyper-Commit Violation Analysis Report"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════════"
    echo
    
    # Flush any pending data
    echo "📊 Flushing violation data..."
    "$TRACKER" flush
    echo
    
    echo "## Summary by Enforcement Level"
    echo "─────────────────────────────────"
    "$TRACKER" summary
    echo
    
    echo "## Timing Analysis (When Do Violations Occur?)"
    echo "──────────────────────────────────────────────"
    "$TRACKER" timing
    echo
    
    echo "## Coverage Gap Analysis (Level 1 vs Level 4)"
    echo "─────────────────────────────────────────────"
    "$TRACKER" gaps
    echo
    
    # Custom queries for deeper insights
    echo "## Most Common Violation Reasons"
    echo "───────────────────────────────────"
    sqlite3 -header -column "$HOME/.local/share/claude-hooks/violations.db" <<'SQL'
SELECT
    violation_reason,
    COUNT(*) as frequency,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM violations WHERE violation_type LIKE '%_block'), 1) as percentage
FROM violations
WHERE violation_type LIKE '%_block'
    AND timestamp >= datetime('now', '-7 days', 'localtime')
    AND violation_reason != ''
GROUP BY violation_reason
ORDER BY frequency DESC
LIMIT 10;
SQL
    echo
    
    echo "## Rapid Edit Sequences (Potential Batch Issues)"
    echo "───────────────────────────────────────────────"
    sqlite3 -header -column "$HOME/.local/share/claude-hooks/violations.db" <<'SQL'
SELECT
    COUNT(*) as rapid_violations,
    ROUND(AVG(time_since_last_op), 1) as avg_gap_seconds,
    violation_reason
FROM violations
WHERE violation_type = 'level1_block'
    AND time_since_last_op < 10
    AND timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY violation_reason
HAVING rapid_violations > 1
ORDER BY rapid_violations DESC;
SQL
    echo
    
    echo "## Operation Sequence Analysis"
    echo "─────────────────────────────"
    sqlite3 -header -column "$HOME/.local/share/claude-hooks/violations.db" <<'SQL'
SELECT
    operation_type,
    COUNT(*) as operations,
    COUNT(CASE WHEN atomic_state_before != atomic_state_after THEN 1 END) as state_changes,
    ROUND(100.0 * COUNT(CASE WHEN atomic_state_before != atomic_state_after THEN 1 END) / COUNT(*), 1) as change_rate_pct
FROM operation_sequence
WHERE timestamp >= datetime('now', '-7 days', 'localtime')
GROUP BY operation_type
ORDER BY operations DESC;
SQL
    echo
    
    echo "## Recommendations"
    echo "─────────────────"
    
    # Analyze patterns and suggest improvements
    local level1_blocks
    local level4_blocks
    local rapid_edits
    
    level1_blocks=$(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT COUNT(*) FROM violations WHERE violation_type = 'level1_block' AND timestamp >= datetime('now', '-7 days', 'localtime');")
    level4_blocks=$(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT COUNT(*) FROM violations WHERE violation_type = 'level4_block' AND timestamp >= datetime('now', '-7 days', 'localtime');")
    rapid_edits=$(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT COUNT(*) FROM violations WHERE violation_type = 'level1_block' AND time_since_last_op < 5 AND timestamp >= datetime('now', '-7 days', 'localtime');")
    
    if [[ "$level4_blocks" -gt "$level1_blocks" ]]; then
        echo "🚨 HIGH PRIORITY: Level 4 blocks ($level4_blocks) exceed Level 1 blocks ($level1_blocks)"
        echo "   → Most violations reach pre-commit. Consider:"
        echo "     • Reducing atomic state cache TTL"
        echo "     • Adding git add interception"
        echo "     • Real-time staging analysis"
        echo
    fi
    
    if [[ "$rapid_edits" -gt 0 ]]; then
        echo "⚡ TIMING ISSUE: $rapid_edits rapid edit violations (<5s between operations)"
        echo "   → Consider batch edit detection or real-time enforcement"
        echo
    fi
    
    local top_reason
    top_reason=$(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT violation_reason FROM violations WHERE violation_type LIKE '%_block' AND timestamp >= datetime('now', '-7 days', 'localtime') GROUP BY violation_reason ORDER BY COUNT(*) DESC LIMIT 1;" 2>/dev/null || echo "unknown")
    
    if [[ -n "$top_reason" && "$top_reason" != "unknown" ]]; then
        echo "🎯 FOCUS AREA: Most common violation reason is '$top_reason'"
        echo "   → Target this specific gap for maximum impact"
        echo
    fi
    
    echo "📈 Data Collection: $(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT COUNT(*) FROM violations;") total events logged"
    echo
}

# Create a live monitoring dashboard
live_monitor() {
    echo "🔴 LIVE: Hyper-Commit Violation Monitor"
    echo "Press Ctrl+C to stop"
    echo "═══════════════════════════════════════════════════════════════"
    
    # Show recent activity every 5 seconds
    while true; do
        clear
        echo "🔴 LIVE: Hyper-Commit Violation Monitor ($(date '+%H:%M:%S'))"
        echo "═══════════════════════════════════════════════════════════════"
        echo
        
        echo "Last 10 Events:"
        sqlite3 -header -column "$HOME/.local/share/claude-hooks/violations.db" "
        SELECT
            substr(timestamp, 12, 8) as time,
            violation_type,
            enforcement_level,
            operation_type,
            substr(violation_reason, 1, 20) as reason
        FROM violations
        ORDER BY id DESC
        LIMIT 10;
        " 2>/dev/null || echo "No data yet..."
        
        echo
        echo "Current Stats (Today):"
        sqlite3 -header -column "$HOME/.local/share/claude-hooks/violations.db" "
        SELECT
            violation_type,
            COUNT(*) as count
        FROM violations
        WHERE date(timestamp) = date('now')
        GROUP BY violation_type;
        " 2>/dev/null || echo "No violations today"
        
        sleep 5
    done
}

# Test the instrumentation
test_instrumentation() {
    echo "🧪 Testing Violation Tracking Instrumentation"
    echo "═══════════════════════════════════════════════════════════════"
    
    # Test direct logging
    echo "1. Testing direct violation logging..."
    "$TRACKER" log "test_violation" "test_enforcement" "test_operation" "test_file.txt" "instrumentation_test"
    
    # Test operation logging
    echo "2. Testing operation logging..."
    "$TRACKER" log-op "test_edit" "test_file.txt"
    
    # Flush and check
    echo "3. Flushing and checking database..."
    "$TRACKER" flush
    
    local test_count
    test_count=$(sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "SELECT COUNT(*) FROM violations WHERE violation_type = 'test_violation';" 2>/dev/null || echo 0)
    
    if [[ "$test_count" -gt 0 ]]; then
        echo "✅ Instrumentation is working! Found $test_count test events."
    else
        echo "❌ Instrumentation failed - no test events in database."
        return 1
    fi
    
    # Clean up test data
    sqlite3 "$HOME/.local/share/claude-hooks/violations.db" "DELETE FROM violations WHERE violation_type = 'test_violation';" 2>/dev/null || true
    echo "🧹 Cleaned up test data."
}

case "${1:-report}" in
    report)
        generate_report
        ;;
    live)
        live_monitor
        ;;
    test)
        test_instrumentation
        ;;
    *)
        echo "Usage: violation-analysis.sh {report|live|test}"
        echo "  report - Generate comprehensive analysis report"
        echo "  live   - Real-time monitoring dashboard"  
        echo "  test   - Test instrumentation setup"
        ;;
esac