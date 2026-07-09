#!/usr/bin/env bash
# Weekly harness-health trend snapshot (closes the R8/N-plan measurement loop).
# Run by cron (Mondays); appends one dated section to a rolling log and sends
# a macOS notification with a one-line digest. Deterministic — no LLM involved.
#
# Tracks the longitudinal targets from the 2026-07-09 antipatterns plan
# (auc-conversion docs/plans/): advisory-injection counts trending down,
# per-session compaction P95 <= 2, gate block counts and latency.
set -uo pipefail

LOG_DIR="$HOME/.claude/metrics"
LOG_FILE="$LOG_DIR/harness-weekly.log"
mkdir -p "$LOG_DIR"

HOOK_METRICS="$HOME/.dotfiles/.claude/hooks/hook-metrics.sh"
PROJECT_DIR="$HOME/.claude/projects/-Users-axos-agallentes-git-auc-conversion"
MEMEVAL="$HOME/git/auc-conversion/scripts/memory-eval/metrics-from-transcripts.sh"

{
  echo ""
  echo "═══ $(date '+%Y-%m-%d %H:%M') ═══════════════════════════════"

  echo "--- hook-metrics (7d) ---"
  if [[ -x "$HOOK_METRICS" || -f "$HOOK_METRICS" ]]; then
    bash "$HOOK_METRICS" summary 2>&1
  else
    echo "hook-metrics.sh missing"
  fi

  echo "--- compactions per session (7d) ---"
  total_compacts=0
  sessions=0
  worst=0
  while IFS= read -r t; do
    sessions=$((sessions + 1))
    c=$(grep -c '"isCompactSummary":true' "$t" 2>/dev/null)
    c=${c:-0}
    total_compacts=$((total_compacts + c))
    [[ "$c" -gt "$worst" ]] && worst=$c
  done < <(find "$PROJECT_DIR" -maxdepth 1 -name '*.jsonl' -mtime -7 -type f 2>/dev/null)
  echo "sessions=$sessions total_compactions=$total_compacts worst_session=$worst"

  echo "--- advisory-injection counts (7d) ---"
  for pat in 'MANDATORY: graphify-out' 'SESSION INIT REQUIRED' 'hook: stack-health' 'hook: plans-health' '<supermemory-recall>'; do
    n=$(grep -l "$pat" "$PROJECT_DIR"/*.jsonl 2>/dev/null | xargs grep -o "$pat" 2>/dev/null | wc -l | tr -d ' ')
    echo "$pat: ${n:-0}"
  done

  echo "--- memory-eval injection overhead (7d) ---"
  if [[ -f "$MEMEVAL" ]]; then
    bash "$MEMEVAL" --days 7 2>/dev/null | tail -8
  else
    echo "memory-eval script missing (repo moved?)"
  fi
} >> "$LOG_FILE"

# One-line digest notification
digest="harness-weekly: ${sessions:-?} sessions, ${total_compacts:-?} compactions (worst ${worst:-?})"
if [[ "${worst:-0}" -gt 2 ]]; then
  digest="⚠️ $digest — compaction target breached (P-worst > 2)"
fi
command -v osascript >/dev/null && osascript -e "display notification \"$digest\" with title \"Harness weekly metrics\"" 2>/dev/null

exit 0
