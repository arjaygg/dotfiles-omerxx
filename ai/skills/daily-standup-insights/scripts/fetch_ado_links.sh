#!/bin/bash
# Fetch GitHub commits and PRs linked to ADO work items (from work item relations).
# Uses same config as fetch_deltas.sh. Run from the skill directory or set SCRIPT_DIR.

set -e
CONFIG_FILE="${CONFIG_FILE:-$HOME/.standup_insights.conf}"
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
MAX_ITEMS="${MAX_ITEMS:-50}"

# Load config
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

TEAM_PROJECT="${1:-${TEAM_PROJECT:-Axos-Universal-Core}}"
AREA_PATH="${2:-${AREA_PATH:-Axos-Universal-Core\AUC Single Account and Sub-Accounting}}"
ORG="${3:-${ORG:-https://dev.azure.com/bofaz}}"
SINCE_DAYS="${4:-${SINCE_DAYS:-2}}"

if [[ "$OSTYPE" == "darwin"* ]]; then
    SINCE_DATE=$(date -v-${SINCE_DAYS}d +"%Y-%m-%d")
else
    SINCE_DATE=$(date -d "${SINCE_DAYS} days ago" +"%Y-%m-%d")
fi

echo "--- GitHub links from ADO work items (Last $SINCE_DAYS Days) ---"
echo "Project: $TEAM_PROJECT | Area: $AREA_PATH"
echo ""

# Get work item IDs from query (JSON). Area path in WIQL uses backslash.
WIQL="SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '$TEAM_PROJECT' AND [System.AreaPath] = '$AREA_PATH' AND [System.ChangedDate] > '$SINCE_DATE' ORDER BY [System.ChangedDate] DESC"
IDS_JSON=$(az boards query --wiql "$WIQL" --org "$ORG" --output json 2>/dev/null)
if ! echo "$IDS_JSON" | jq -e 'type == "array"' >/dev/null 2>&1; then
    echo "Could not run query or parse results."
    exit 1
fi

IDS=$(echo "$IDS_JSON" | jq -r '.[].id' | head -n "$MAX_ITEMS")
COUNT=$(echo "$IDS" | grep -c . || true)
if [ "$COUNT" -eq 0 ]; then
    echo "No work items found."
    exit 0
fi

echo "Checking relations for $COUNT work item(s) (max $MAX_ITEMS)..."
echo ""

while IFS= read -r id; do
    [ -z "$id" ] && continue
    WI=$(az boards work-item show --id "$id" --org "$ORG" --expand relations --output json 2>/dev/null) || continue
    TITLE=$(echo "$WI" | jq -r '.fields["System.Title"] // .fields["System.Id"] // $id' --arg id "$id")
    RELATIONS=$(echo "$WI" | jq -r '.relations // []')
    COMMITS=$(echo "$RELATIONS" | jq -r '.[] | select(.rel == "ArtifactLink" and (.attributes.name == "GitHub Commit")) | .url' 2>/dev/null | while read -r url; do
        # vstfs:///GitHub/Commit/{repo-guid}%2f{commit-sha}
        [[ "$url" =~ %2f([a-f0-9]+)$ ]] && echo "${BASH_REMATCH[1]:0:7}"
    done | tr '\n' ' ' | xargs)
    PRS=$(echo "$RELATIONS" | jq -r '.[] | select(.rel == "ArtifactLink" and (.attributes.name == "GitHub Pull Request")) | .url' 2>/dev/null | while read -r url; do
        # vstfs:///GitHub/PullRequest/{repo-guid}%2f{pr-number}
        [[ "$url" =~ %2f([0-9]+)$ ]] && echo "#${BASH_REMATCH[1]}"
    done | tr '\n' ' ' | xargs)

    if [ -n "$COMMITS" ] || [ -n "$PRS" ]; then
        echo "  $id | ${TITLE:0:60}"
        [ -n "$COMMITS" ] && echo "    Commits: $COMMITS"
        [ -n "$PRS" ]     && echo "    PRs:     $PRS"
        echo ""
    fi
done <<< "$IDS"

echo "Done. (Git links are stored on work items when commits/PRs reference AB#<id> or the item is linked in the UI.)"
