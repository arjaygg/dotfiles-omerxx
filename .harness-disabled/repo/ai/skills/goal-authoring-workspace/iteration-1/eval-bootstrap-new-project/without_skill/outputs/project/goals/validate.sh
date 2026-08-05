#!/usr/bin/env bash
# Validate that every goal doc in this directory is well-formed.
# Usage: ./goals/validate.sh
# Exit 0 = all goals valid; exit 1 = one or more problems found.

set -euo pipefail

# Resolve the goals directory relative to this script, so it works from any cwd.
GOALS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Required front-matter keys and required section headings.
REQUIRED_KEYS=(id title status owner created updated)
REQUIRED_SECTIONS=("## Context" "## Objective" "## Success Criteria" "## Milestones" "## Risks")
VALID_STATUSES="proposed active blocked done abandoned"

errors=0
checked=0

shopt -s nullglob
goal_files=("$GOALS_DIR"/goal-*.md)

if [ ${#goal_files[@]} -eq 0 ]; then
  echo "WARN: no goal-*.md files found in $GOALS_DIR"
  exit 0
fi

for f in "${goal_files[@]}"; do
  name="$(basename "$f")"
  checked=$((checked + 1))
  file_ok=1

  # Filename convention: goal-NN-slug.md
  if ! [[ "$name" =~ ^goal-[0-9]{2}-[a-z0-9-]+\.md$ ]]; then
    echo "FAIL: $name — filename must match goal-NN-slug.md"
    file_ok=0
  fi

  # Front matter must be the first line.
  if [ "$(head -n 1 "$f")" != "---" ]; then
    echo "FAIL: $name — must start with a '---' front-matter block"
    file_ok=0
  fi

  # Required front-matter keys.
  front_matter="$(awk 'NR==1 && $0=="---"{f=1;next} f&&$0=="---"{exit} f' "$f")"
  for key in "${REQUIRED_KEYS[@]}"; do
    if ! grep -q "^${key}:" <<<"$front_matter"; then
      echo "FAIL: $name — missing front-matter key: $key"
      file_ok=0
    fi
  done

  # Status must be one of the allowed values.
  status_val="$(grep '^status:' <<<"$front_matter" | head -n1 | sed 's/^status:[[:space:]]*//')"
  if [ -n "$status_val" ] && ! grep -qw "$status_val" <<<"$VALID_STATUSES"; then
    echo "FAIL: $name — invalid status '$status_val' (allowed: $VALID_STATUSES)"
    file_ok=0
  fi

  # Required sections.
  for section in "${REQUIRED_SECTIONS[@]}"; do
    if ! grep -qF "$section" "$f"; then
      echo "FAIL: $name — missing section: $section"
      file_ok=0
    fi
  done

  if [ "$file_ok" -eq 1 ]; then
    echo "OK:   $name"
  else
    errors=$((errors + 1))
  fi
done

echo "---"
if [ "$errors" -eq 0 ]; then
  echo "All $checked goal(s) valid."
  exit 0
else
  echo "$errors of $checked goal(s) failed validation."
  exit 1
fi
