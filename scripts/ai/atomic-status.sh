#!/usr/bin/env bash
# Canonical machine-readable repo state check for hyper-atomic continuation.
# Outputs one of: in_progress | blocked | overgrown | ready_to_commit
# Always exits 0 — state is communicated via stdout.
#
# Override defaults per-repo by placing .claude-atomic.yaml at the repo root.
# See ~/.dotfiles/scripts/ai/atomic-status.sh for format.
set -euo pipefail

# Default thresholds (overridable via env or .claude-atomic.yaml)
MAX_FILES=${ATOMIC_MAX_FILES:-7}
MAX_SUBSYSTEMS=${ATOMIC_MAX_SUBSYSTEMS:-3}
MAX_DIFF_LINES=${ATOMIC_MAX_DIFF_LINES:-300}

# Staged files only (what will be committed)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$STAGED_FILES" ]]; then
    echo "in_progress"
    exit 0
fi

FILE_COUNT=$(echo "$STAGED_FILES" | wc -l | tr -d ' ')
DIFF_LINES=$(git diff --cached --numstat 2>/dev/null | awk '{sum+=$1+$2} END {print sum+0}')

# --- Load per-repo override if .claude-atomic.yaml exists ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
OVERRIDE_FILE="$REPO_ROOT/.claude-atomic.yaml"

# Parse thresholds from YAML override (simple key: value parsing, no yq required)
if [[ -f "$OVERRIDE_FILE" ]]; then
    _max_files=$(grep -E '^\s+max_files:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    _max_subsystems=$(grep -E '^\s+max_subsystems:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    _max_diff_lines=$(grep -E '^\s+max_diff_lines:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    [[ -n "$_max_files" ]] && MAX_FILES="$_max_files"
    [[ -n "$_max_subsystems" ]] && MAX_SUBSYSTEMS="$_max_subsystems"
    [[ -n "$_max_diff_lines" ]] && MAX_DIFF_LINES="$_max_diff_lines"
fi

# --- Generic subsystem category detection ---
# Each file is assigned to the first matching category.
# Category counts are used for mixed-concern detection.
declare -A CATEGORY_HITS

categorize_file() {
    local f="$1"
    local base
    base=$(basename "$f")
    local dir
    dir=$(dirname "$f")

    # tests
    if [[ "$dir" == tests* || "$dir" == test* || "$dir" == spec* || "$dir" == __tests__* \
       || "$base" == *_test.* || "$base" == *.spec.* || "$base" == *.test.* ]]; then
        echo "tests"; return
    fi
    # ui
    if [[ "$dir" == ui/* || "$dir" == frontend/* || "$dir" == web/* \
       || "$base" == *.css || "$base" == *.html || "$base" == *.svelte || "$base" == *.vue ]]; then
        echo "ui"; return
    fi
    # source code
    if [[ "$dir" == src/* || "$dir" == lib/* || "$dir" == app/* || "$dir" == pkg/* || "$dir" == cmd/* \
       || "$base" == *.rs || "$base" == *.go || "$base" == *.ts || "$base" == *.tsx \
       || "$base" == *.py || "$base" == *.js || "$base" == *.jsx || "$base" == *.rb \
       || "$base" == *.java || "$base" == *.kt || "$base" == *.swift || "$base" == *.cpp || "$base" == *.c ]]; then
        echo "source"; return
    fi
    # infra
    if [[ "$dir" == scripts/* || "$dir" == ci/* || "$dir" == .github/* \
       || "$base" == "setup.sh" || "$base" == "Brewfile" || "$base" == "Makefile" \
       || "$base" == "Dockerfile" || "$base" == ".dockerignore" ]]; then
        echo "infra"; return
    fi
    # config
    if [[ "$base" == *.toml || "$base" == *.yaml || "$base" == *.yml \
       || "$base" == *.json || "$base" == .env* || "$base" == *.ini || "$base" == *.cfg ]]; then
        echo "config"; return
    fi
    # docs
    if [[ "$dir" == docs/* || "$dir" == decisions/* || "$dir" == plans/* \
       || "$base" == *.md || "$base" == *.txt || "$base" == *.rst ]]; then
        echo "docs"; return
    fi
    # fallback: top-level dir as subsystem
    if [[ "$dir" != "." ]]; then
        echo "${dir%%/*}"; return
    fi
    echo "root"
}

DOCS_ONLY=1
declare -A SEEN_CATEGORIES

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    cat=$(categorize_file "$file")
    SEEN_CATEGORIES["$cat"]=1
    if [[ "$cat" != "docs" ]]; then
        DOCS_ONLY=0
    fi
done <<< "$STAGED_FILES"

CATEGORY_COUNT=${#SEEN_CATEGORIES[@]}

# Docs-only exemption: more lenient thresholds
if [[ "$DOCS_ONLY" -eq 1 ]]; then
    MAX_FILES=30
    MAX_DIFF_LINES=1000
fi

# Mixed concern: 3+ distinct categories = blocked
if [[ "$CATEGORY_COUNT" -ge "$MAX_SUBSYSTEMS" ]]; then
    echo "blocked"
    exit 0
fi

# Overgrown: too many files or diff lines
if [[ "$FILE_COUNT" -gt "$MAX_FILES" ]] || [[ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]]; then
    echo "overgrown"
    exit 0
fi

echo "in_progress"
