#!/usr/bin/env bash
# PreToolUse hook: Enforce plan file naming convention
# Runs before Write operations to ensure plan files follow YYYY-MM-DD-context.md format

set -euo pipefail

# Read hook input from stdin
input=$(cat)
tool_name=$(echo "$input" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_name', ''))")
file_path=$(echo "$input" | python3 -c "import sys, json; print(json.load(sys.stdin).get('parameters', {}).get('path', ''))")

# Only process Write operations
[[ "$tool_name" == "Write" ]] || exit 0
[[ -n "$file_path" ]] || exit 0

# Check if this is a plan file (in plans/ directory and .md extension)
[[ "$file_path" == *"/plans/"* || "$file_path" == "plans/"* ]] || exit 0
[[ "$file_path" == *".md" ]] || exit 0

# Extract filename from path
filename=$(basename "$file_path")

# Check if filename follows YYYY-MM-DD-context.md pattern
if [[ "$filename" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-.+\.md$ ]]; then
    # Already follows convention, allow it
    exit 0
fi

# Check if it's a random generated name that needs fixing
if [[ "$filename" =~ ^[a-z]+-[a-z]+-[a-z]+\.md$ ]]; then
    # Generate suggested name based on current date
    today=$(date '+%Y-%m-%d')
    
    echo "[PLAN NAMING] File \"$filename\" doesn't follow naming convention." >&2
    echo "Expected format: YYYY-MM-DD-context.md" >&2
    echo "Suggestion: $today-your-task-description.md" >&2
    echo "Please rename the file to follow the convention in CLAUDE.md" >&2
    
    # Don't block the operation, just warn
    exit 0
fi

# For other non-conforming names, provide guidance
if [[ ! "$filename" =~ ^(active-context|decisions|progress|session-handoff) ]]; then
    today=$(date '+%Y-%m-%d')
    echo "[PLAN NAMING] Plan file \"$filename\" should follow YYYY-MM-DD-context.md format." >&2
    echo "Example: $today-refactor-auth-flow.md" >&2
fi

exit 0