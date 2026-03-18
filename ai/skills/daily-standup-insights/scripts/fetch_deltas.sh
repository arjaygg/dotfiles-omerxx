#!/bin/bash

CONFIG_FILE="$HOME/.standup_insights.conf"

# Load previous values if config exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Override with parameters if provided, otherwise fallback to loaded values or defaults
TEAM_PROJECT="${1:-${TEAM_PROJECT:-Axos-Universal-Core}}"
AREA_PATH="${2:-${AREA_PATH:-Axos-Universal-Core\AUC Single Account and Sub-Accounting}}"
ORG="${3:-${ORG:-https://dev.azure.com/bofaz}}"
SINCE_DAYS="${4:-${SINCE_DAYS:-2}}"

# Save current values for next time
echo "TEAM_PROJECT=\"$TEAM_PROJECT\"" > "$CONFIG_FILE"
echo "AREA_PATH=\"$AREA_PATH\"" >> "$CONFIG_FILE"
echo "ORG=\"$ORG\"" >> "$CONFIG_FILE"
echo "SINCE_DAYS=\"$SINCE_DAYS\"" >> "$CONFIG_FILE"

# Date calculation for ADO (Last N days)
# Using a portable date approach
if [[ "$OSTYPE" == "darwin"* ]]; then
    SINCE_DATE=$(date -v-${SINCE_DAYS}d +"%Y-%m-%dT%H:%M:%SZ")
else
    SINCE_DATE=$(date -d "${SINCE_DAYS} days ago" +"%Y-%m-%dT%H:%M:%SZ")
fi

echo "--- ADO Activity (Last $SINCE_DAYS Days) ---"
echo "Project: $TEAM_PROJECT | Area: $AREA_PATH"
az boards query --wiql "SELECT [System.Id], [System.WorkItemType], [System.Title], [System.State], [System.AssignedTo], [System.ChangedDate] FROM WorkItems WHERE [System.TeamProject] = '$TEAM_PROJECT' AND [System.AreaPath] = '$AREA_PATH' AND [System.ChangedDate] > '$SINCE_DATE' ORDER BY [System.ChangedDate] DESC" --org "$ORG" --output table

echo -e "\n--- Git Activity (Last $SINCE_DAYS Days) ---"
git log --since="$SINCE_DAYS days ago" --pretty=format:"%h | %an | %s"

echo -e "\n--- ADO IDs found in recent Commits ---"
git log --since="$SINCE_DAYS days ago" --pretty=format:"%s" | grep -oE "[0-9]{6,7}" | sort -u
