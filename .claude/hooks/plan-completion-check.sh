#!/usr/bin/env bash
# Stop hook — fires at the end of every agent turn.
# Warns if the active plan has incomplete steps.
#
# NOTE: The Stop event fires on EVERY turn end, not just true session end.
# Guard: skip if less than half the plan steps are addressed, to avoid
# noise on early turns when the plan is still being worked through.

PLAN=$(grep "^plan:" plans/active-context.md 2>/dev/null | awk '{print $2}')
[ -z "$PLAN" ] || [ ! -f "$PLAN" ] && exit 0

# Superpowers Inline-Review Enforcement
if grep -qE "TBD|TODO|// \.\.\. existing code" plans/active-context.md 2>/dev/null; then
  echo "SUPERPOWERS CHECK FAILED: plans/active-context.md contains placeholders (TBD/TODO/existing code)." >&2
  echo "Rewrite the plan to be comprehensive and explicit." >&2
fi

TOTAL_STEPS=$(grep -c "^## Step" "$PLAN" 2>/dev/null || true)
TOTAL_STEPS=$(printf '%s\n' "${TOTAL_STEPS:-0}" | tail -n1)
[ "$TOTAL_STEPS" -eq 0 ] && exit 0

DONE=$(grep -c "^- \[x\]" plans/progress.md 2>/dev/null || true)
DONE=$(printf '%s\n' "${DONE:-0}" | tail -n1)
INCOMPLETE=$(grep -c "^- \[ \]" plans/progress.md 2>/dev/null || true)
INCOMPLETE=$(printf '%s\n' "${INCOMPLETE:-0}" | tail -n1)

# Skip if less than half the plan is complete (likely mid-task turn)
[ "$DONE" -lt $(( TOTAL_STEPS / 2 )) ] && exit 0

if [ "$INCOMPLETE" -gt 0 ]; then
  echo "PLAN CHECK: $INCOMPLETE step(s) still incomplete in $PLAN" >&2
  echo "Review plans/progress.md before marking the task done." >&2
fi

exit 0
