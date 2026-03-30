#!/usr/bin/env bash
# Stop hook — fires at the end of every agent turn.
# Warns if the active plan has incomplete steps.
#
# NOTE: The Stop event fires on EVERY turn end, not just true session end.
# Guard: skip if less than half the plan steps are addressed, to avoid
# noise on early turns when the plan is still being worked through.

PLAN=$(grep "^plan:" plans/active-context.md 2>/dev/null | awk '{print $2}')
[ -z "$PLAN" ] || [ ! -f "$PLAN" ] && exit 0

TOTAL_STEPS=$(grep -c "^## Step" "$PLAN" 2>/dev/null || echo 0)
[ "$TOTAL_STEPS" -eq 0 ] && exit 0

DONE=$(grep -c "^- \[x\]" plans/progress.md 2>/dev/null || echo 0)
INCOMPLETE=$(grep -c "^- \[ \]" plans/progress.md 2>/dev/null || echo 0)

# Skip if less than half the plan is complete (likely mid-task turn)
[ "$DONE" -lt $(( TOTAL_STEPS / 2 )) ] && exit 0

if [ "$INCOMPLETE" -gt 0 ]; then
  echo "PLAN CHECK: $INCOMPLETE step(s) still incomplete in $PLAN" >&2
  echo "Review plans/progress.md before marking the task done." >&2
fi

exit 0
