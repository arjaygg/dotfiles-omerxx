#!/usr/bin/env bash
# check-skill-drift.sh — guard against drift in agent skill directories
#
# Exits 0 when all entries are valid skill symlinks or quarantined real dirs
# (quarantined = SKILL.md has disable-model-invocation: true).
# Exits 1 when a dangling symlink, symlink without a skill file, or non-quarantined real dir is found.
#
# Usage:
#   scripts/check-skill-drift.sh                         # check from repo root
#   scripts/check-skill-drift.sh DIR [DIR ...]           # check one or more skill dirs
#   scripts/check-skill-drift.sh --prune-stale-links DIR # remove invalid symlinks only
#   scripts/check-skill-drift.sh --plant-test            # plant a test dir and verify

set -euo pipefail

DEFAULT_SKILLS_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.claude/skills"
PRUNE_STALE_LINKS=0

if [[ "${1:-}" == "--prune-stale-links" ]]; then
    PRUNE_STALE_LINKS=1
    shift
fi

if [[ "${1:-}" == "--plant-test" ]]; then
    SKILLS_DIR="$DEFAULT_SKILLS_DIR"
    TMPDIR_PLANTED=$(mktemp -d "$SKILLS_DIR/test-drift-XXXXXX")
    trap 'rm -rf "$TMPDIR_PLANTED"' EXIT
    echo "Planted test dir: $TMPDIR_PLANTED"
    set -- "$SKILLS_DIR"
fi

REAL_DIR_VIOLATIONS=()
DANGLING_SYMLINKS=()
SYMLINK_TARGET_VIOLATIONS=()
SKILLS_DIRS=("$@")

if [[ ${#SKILLS_DIRS[@]} -eq 0 ]]; then
    SKILLS_DIRS=("$DEFAULT_SKILLS_DIR")
fi

shopt -s nullglob

for skills_dir in "${SKILLS_DIRS[@]}"; do
    for entry in "$skills_dir"/*; do
        name="$(basename "$entry")"

        if [[ -L "$entry" ]]; then
            if [[ ! -e "$entry" ]]; then
                DANGLING_SYMLINKS+=("$skills_dir/$name")
            elif [[ ! -f "$entry/SKILL.md" && ! -f "$entry/skill.md" ]]; then
                SYMLINK_TARGET_VIOLATIONS+=("$skills_dir/$name")
            fi
            continue
        fi

        [[ -d "$entry" ]] || continue

        skill_md="$entry/SKILL.md"
        if [[ -f "$skill_md" ]] && grep -q "disable-model-invocation: true" "$skill_md" 2>/dev/null; then
            echo "QUARANTINED (ok): $skills_dir/$name"
            continue
        fi

        REAL_DIR_VIOLATIONS+=("$skills_dir/$name")
    done
done

if [[ ${#REAL_DIR_VIOLATIONS[@]} -eq 0 && ${#DANGLING_SYMLINKS[@]} -eq 0 && ${#SYMLINK_TARGET_VIOLATIONS[@]} -eq 0 ]]; then
    echo "✅ skill dirs — all entries are valid skill symlinks or quarantined"
    exit 0
fi

if [[ "$PRUNE_STALE_LINKS" -eq 1 ]]; then
    PRUNED=()
    for v in "${DANGLING_SYMLINKS[@]}" "${SYMLINK_TARGET_VIOLATIONS[@]}"; do
        [[ -L "$v" ]] || continue
        rm "$v"
        PRUNED+=("$v")
    done

    if [[ ${#PRUNED[@]} -gt 0 ]]; then
        echo "Pruned stale skill symlinks:"
        for v in "${PRUNED[@]}"; do
            echo "  - $v"
        done
    fi

    DANGLING_SYMLINKS=()
    SYMLINK_TARGET_VIOLATIONS=()

    if [[ ${#REAL_DIR_VIOLATIONS[@]} -eq 0 ]]; then
        echo "✅ skill dirs — all entries are valid skill symlinks or quarantined"
        exit 0
    fi
fi

if [[ ${#DANGLING_SYMLINKS[@]} -gt 0 ]]; then
    echo "❌ Dangling symlinks found in skill dirs:" >&2
    for v in "${DANGLING_SYMLINKS[@]}"; do
        echo "  - $v" >&2
    done
    echo "" >&2
    echo "Fix: restore the target under ai/skills/ or remove the stale symlink." >&2
fi

if [[ ${#SYMLINK_TARGET_VIOLATIONS[@]} -gt 0 ]]; then
    echo "❌ Symlink targets without SKILL.md or skill.md found in skill dirs:" >&2
    for v in "${SYMLINK_TARGET_VIOLATIONS[@]}"; do
        echo "  - $v" >&2
    done
    echo "" >&2
    echo "Fix: point the symlink at a real skill directory, add SKILL.md/skill.md, or remove the stale symlink." >&2
fi

if [[ ${#REAL_DIR_VIOLATIONS[@]} -gt 0 ]]; then
    echo "❌ Non-quarantined real directories found in skill dirs:" >&2
    for v in "${REAL_DIR_VIOLATIONS[@]}"; do
        echo "  - $v" >&2
    done
    echo "" >&2
    echo "Fix: move contents to ai/skills/, then replace with a symlink:" >&2
    echo "  ln -sfn '<canonical-skill-dir>' '<target-skill-dir>/<name>'" >&2
    echo "Or quarantine by adding 'disable-model-invocation: true' to its SKILL.md frontmatter." >&2
fi
exit 1
