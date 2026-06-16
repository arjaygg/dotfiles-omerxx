#!/usr/bin/env bash
# check-skill-drift.sh — guard against real directories in .claude/skills/
#
# Exits 0 when all entries are symlinks or quarantined real dirs
# (quarantined = SKILL.md has disable-model-invocation: true).
# Exits 1 when a non-quarantined real dir is found.
#
# Usage:
#   scripts/check-skill-drift.sh                    # check from repo root
#   scripts/check-skill-drift.sh --plant-test       # plant a test dir and verify

set -euo pipefail

SKILLS_DIR="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.claude/skills}"

if [[ "${1:-}" == "--plant-test" ]]; then
    TMPDIR_PLANTED=$(mktemp -d "$SKILLS_DIR/test-drift-XXXXXX")
    trap 'rm -rf "$TMPDIR_PLANTED"' EXIT
    echo "Planted test dir: $TMPDIR_PLANTED"
fi

VIOLATIONS=()

for entry in "$SKILLS_DIR"/*/; do
    entry="${entry%/}"
    name=$(basename "$entry")

    # Skip if it's a symlink (correct state)
    [[ -L "$entry" ]] && continue

    # It's a real directory. Check if quarantined.
    skill_md="$entry/SKILL.md"
    if [[ -f "$skill_md" ]] && grep -q "disable-model-invocation: true" "$skill_md" 2>/dev/null; then
        echo "QUARANTINED (ok): $name"
        continue
    fi

    VIOLATIONS+=("$name")
done

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
    echo "✅ .claude/skills/ — all entries are symlinks or quarantined"
    exit 0
fi

echo "❌ Non-quarantined real directories found in .claude/skills/:" >&2
for v in "${VIOLATIONS[@]}"; do
    echo "  - $v" >&2
done
echo "" >&2
echo "Fix: move contents to ai/skills/, then replace with a symlink:" >&2
echo "  ln -sfn '../../ai/skills/<name>' .claude/skills/<name>" >&2
echo "Or quarantine by adding 'disable-model-invocation: true' to its SKILL.md frontmatter." >&2
exit 1
