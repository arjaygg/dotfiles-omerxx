#!/usr/bin/env bash
# Checks for drift between ai/skills/ (canonical) and .claude/skills/ (distribution).
# Exits non-zero if any skill is unlinked, uses absolute symlinks, or points to a missing target.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
src="$repo_root/ai/skills"
dst="$repo_root/.claude/skills"

failures=0

for skill_dir in "$src"/*/; do
    [ -d "$skill_dir" ] || continue
    { [ -f "${skill_dir}SKILL.md" ] || [ -f "${skill_dir}skill.md" ]; } || continue
    name="$(basename "${skill_dir%/}")"
    link="$dst/$name"

    if [ ! -e "$link" ] && [ ! -L "$link" ]; then
        printf 'FAIL: unlinked skill: %s\n' "$name" >&2
        failures=$((failures + 1))
        continue
    fi

    if [ ! -L "$link" ]; then
        printf 'FAIL: %s is a real file/dir, not a symlink\n' "$name" >&2
        failures=$((failures + 1))
        continue
    fi

    target="$(readlink "$link")"
    if [[ "$target" == /* ]]; then
        printf 'FAIL: %s uses absolute symlink: %s\n' "$name" "$target" >&2
        failures=$((failures + 1))
        continue
    fi

    if [ ! -d "$link" ]; then
        printf 'FAIL: %s symlink is broken (target missing)\n' "$name" >&2
        failures=$((failures + 1))
        continue
    fi

    printf 'OK: %s\n' "$name"
done

if [ "$failures" -ne 0 ]; then
    printf '\n%d skill(s) failed drift check\n' "$failures" >&2
    exit 1
fi
printf '\nAll skills are correctly linked.\n'
