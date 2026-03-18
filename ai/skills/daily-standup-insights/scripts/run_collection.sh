#!/bin/bash
# Orchestrator: runs fetch_ado_links.sh (always) and fetch_deltas.sh (when cwd is a git repo).
# Use from skill dir for ADO links only; run from team repo to get both ADO links and local Git deltas.
# Same args as both scripts: TEAM_PROJECT AREA_PATH ORG SINCE_DAYS

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TEAM_PROJECT="${1:-${TEAM_PROJECT:-Axos-Universal-Core}}"
AREA_PATH="${2:-${AREA_PATH:-Axos-Universal-Core\AUC Single Account and Sub-Accounting}}"
ORG="${3:-${ORG:-https://dev.azure.com/bofaz}}"
SINCE_DAYS="${4:-${SINCE_DAYS:-2}}"

# Always run ADO links (no repo needed)
"$SCRIPT_DIR/fetch_ado_links.sh" "$TEAM_PROJECT" "$AREA_PATH" "$ORG" "$SINCE_DAYS"

# If cwd is a git repo, run fetch_deltas (needs git log)
if [ -d .git ]; then
  "$SCRIPT_DIR/fetch_deltas.sh" "$TEAM_PROJECT" "$AREA_PATH" "$ORG" "$SINCE_DAYS"
else
  echo "--- Skipping fetch_deltas (not in a git repo). Run from team repo to include local Git deltas. ---"
fi
