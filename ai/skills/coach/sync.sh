#!/usr/bin/env bash
# Syncs AI Engineering Coach rules from microsoft/AI-Engineering-Coach.
# Run this once after install, and again whenever you want to pick up upstream updates.
# Usage: bash sync.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_DIR="$SKILL_DIR/rules"

if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI is required. Install from https://cli.github.com" >&2
  exit 1
fi

mkdir -p "$RULES_DIR"

echo "Fetching rule file list from microsoft/AI-Engineering-Coach..."
rule_paths=$(gh api "repos/microsoft/AI-Engineering-Coach/git/trees/main?recursive=1" \
  --jq '.tree[] | select(.path | startswith("src/core/rules/")) | .path')

count=0
while IFS= read -r path; do
  name=$(basename "$path")
  gh api "repos/microsoft/AI-Engineering-Coach/contents/$path" \
    --jq '.content' | base64 -d > "$RULES_DIR/$name"
  count=$((count + 1))
done <<< "$rule_paths"

echo "Fetching coaching persona..."
gh api "repos/microsoft/AI-Engineering-Coach/contents/src/chat/system-prompt.ts" \
  --jq '.content' | base64 -d > "$SKILL_DIR/coach-persona.ts"

echo "Synced $count rules to $RULES_DIR"
echo "Persona written to $SKILL_DIR/coach-persona.ts"
