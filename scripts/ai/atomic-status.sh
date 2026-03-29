#!/usr/bin/env bash
# Canonical machine-readable repo state check for hyper-atomic continuation.
# Outputs one of: in_progress | blocked | overgrown | ready_to_commit
# Always exits 0 — state is communicated via stdout.
#
# Flags:
#   --verbose   Print diagnostic report to stderr (stdout unchanged)
#   --json      Print full state as JSON to stdout (replaces bare state word)
#
# Override defaults per-repo by placing .claude-atomic.yaml at the repo root.
# YAML format (constrained — indent-2 keys, indent-4 dash-prefixed values):
#
#   subsystems:
#     category-name:
#       - "path/prefix/"
#       - "exact-file.ext"
#   thresholds:
#     max_files: 7
#     max_subsystems: 3
#     max_diff_lines: 300
#   limits:
#     max_file_size_kb: 500
set -euo pipefail

VERBOSE=0
JSON_MODE=0
for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=1 ;;
        --json) JSON_MODE=1 ;;
    esac
done

# Default thresholds (overridable via env or .claude-atomic.yaml)
MAX_FILES=${ATOMIC_MAX_FILES:-7}
MAX_SUBSYSTEMS=${ATOMIC_MAX_SUBSYSTEMS:-3}
MAX_DIFF_LINES=${ATOMIC_MAX_DIFF_LINES:-300}

# Staged files only (what will be committed)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$STAGED_FILES" ]]; then
    if [[ "$JSON_MODE" -eq 1 ]]; then
        echo '{"state":"in_progress","staged_files":0,"diff_lines":0,"subsystem_count":0,"subsystems":{},"exceeded":[]}'
    else
        echo "in_progress"
    fi
    exit 0
fi

FILE_COUNT=$(echo "$STAGED_FILES" | wc -l | tr -d ' ')
DIFF_LINES=$(git diff --cached --numstat 2>/dev/null | awk '{sum+=$1+$2} END {print sum+0}')

# --- Load per-repo override if .claude-atomic.yaml exists ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
OVERRIDE_FILE="$REPO_ROOT/.claude-atomic.yaml"

# Flag for custom subsystem parsing
USE_CUSTOM_SUBSYSTEMS=0
declare -a CUSTOM_CAT_NAMES=()
declare -a CUSTOM_CAT_PATTERNS=()

if [[ -f "$OVERRIDE_FILE" ]]; then
    # Parse thresholds (simple key: value parsing, no yq required)
    _max_files=$(grep -E '^\s+max_files:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    _max_subsystems=$(grep -E '^\s+max_subsystems:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    _max_diff_lines=$(grep -E '^\s+max_diff_lines:' "$OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    [[ -n "$_max_files" ]] && MAX_FILES="$_max_files"
    [[ -n "$_max_subsystems" ]] && MAX_SUBSYSTEMS="$_max_subsystems"
    [[ -n "$_max_diff_lines" ]] && MAX_DIFF_LINES="$_max_diff_lines"

    # Parse subsystems block (constrained YAML: indent-2 = category, indent-4 = dash pattern)
    # Format:
    #   subsystems:
    #     category-name:
    #       - "path/prefix/"
    _current_cat=""
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue

        # Detect top-level keys (no indent) — stop if we leave subsystems block
        if [[ "$line" =~ ^[a-z] && "$line" != "subsystems:" ]]; then
            [[ -n "$_current_cat" ]] && break
            continue
        fi

        # Start of subsystems block
        [[ "$line" == "subsystems:" ]] && { USE_CUSTOM_SUBSYSTEMS=1; continue; }

        # Category name (indent-2, ends with colon)
        if [[ "$line" =~ ^[[:space:]]{2}[a-zA-Z] && "$line" =~ :$ ]]; then
            _current_cat=$(echo "$line" | sed 's/^[[:space:]]*//' | sed 's/:$//')
            continue
        fi

        # Pattern entry (indent-4+, starts with dash)
        if [[ -n "$_current_cat" && "$line" =~ ^[[:space:]]+- ]]; then
            _pattern=$(echo "$line" | sed 's/^[[:space:]]*-[[:space:]]*//' | sed 's/^"//' | sed 's/"$//')
            CUSTOM_CAT_NAMES+=("$_current_cat")
            CUSTOM_CAT_PATTERNS+=("$_pattern")
        fi
    done < "$OVERRIDE_FILE"
fi

# --- Subsystem category detection ---
# Each file is assigned to the first matching category.

categorize_file_custom() {
    local f="$1"
    local i
    for i in "${!CUSTOM_CAT_PATTERNS[@]}"; do
        local pattern="${CUSTOM_CAT_PATTERNS[$i]}"
        # Prefix match: file path starts with pattern
        if [[ "$f" == "$pattern"* || "$f" == *"/$pattern"* ]]; then
            echo "${CUSTOM_CAT_NAMES[$i]}"
            return
        fi
    done
    echo "other"
}

categorize_file_generic() {
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

categorize_file() {
    if [[ "$USE_CUSTOM_SUBSYSTEMS" -eq 1 ]]; then
        categorize_file_custom "$1"
    else
        categorize_file_generic "$1"
    fi
}

# --- Categorize all staged files ---
DOCS_ONLY=1
declare -A SEEN_CATEGORIES
declare -A CATEGORY_FILES  # cat -> "file1 file2 ..."

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    cat=$(categorize_file "$file")
    SEEN_CATEGORIES["$cat"]=1
    CATEGORY_FILES["$cat"]+="$file "
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

# --- Determine state ---
EXCEEDED=()
STATE=""

if [[ "$CATEGORY_COUNT" -ge "$MAX_SUBSYSTEMS" ]]; then
    STATE="blocked"
    EXCEEDED+=("max_subsystems")
elif [[ "$FILE_COUNT" -gt "$MAX_FILES" ]] || [[ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]]; then
    STATE="overgrown"
    [[ "$FILE_COUNT" -gt "$MAX_FILES" ]] && EXCEEDED+=("max_files")
    [[ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]] && EXCEEDED+=("max_diff_lines")
else
    STATE="ready_to_commit"
fi

# --- Intent drift detection (advisory, verbose/json only) ---
INTENT_DRIFT=""
INTENT_FILE="$REPO_ROOT/.claude-atomic-intent"
if [[ -f "$INTENT_FILE" && ( "$VERBOSE" -eq 1 || "$JSON_MODE" -eq 1 ) ]]; then
    LAST_SCOPE=$(grep '^LAST_COMMIT_SCOPE=' "$INTENT_FILE" 2>/dev/null | cut -d= -f2 || true)
    if [[ -n "$LAST_SCOPE" ]]; then
        _total=0
        _mismatched=0
        while IFS= read -r _f; do
            [[ -z "$_f" ]] && continue
            (( _total++ )) || true
            if [[ "$_f" != *"$LAST_SCOPE"* ]]; then
                (( _mismatched++ )) || true
            fi
        done <<< "$STAGED_FILES"
        if [[ "$_total" -gt 0 ]]; then
            _pct=$(( _mismatched * 100 / _total ))
            if [[ "$_pct" -gt 50 ]]; then
                LAST_TYPE=$(grep '^LAST_COMMIT_TYPE=' "$INTENT_FILE" 2>/dev/null | cut -d= -f2 || true)
                INTENT_DRIFT="last commit was ${LAST_TYPE}(${LAST_SCOPE}), ${_pct}% of staged files don't match scope"
            fi
        fi
    fi
fi

# --- Output ---
if [[ "$JSON_MODE" -eq 1 ]]; then
    # Build JSON subsystems object
    _json_subs="{"
    _first=1
    for _cat in "${!CATEGORY_FILES[@]}"; do
        _files="${CATEGORY_FILES[$_cat]}"
        _count=$(echo "$_files" | wc -w | tr -d ' ')
        [[ $_first -eq 0 ]] && _json_subs+=","
        _first=0
        # Escape file list as JSON array
        _json_arr="["
        _ffirst=1
        for _ff in $_files; do
            [[ -z "$_ff" ]] && continue
            [[ $_ffirst -eq 0 ]] && _json_arr+=","
            _ffirst=0
            _json_arr+="\"$_ff\""
        done
        _json_arr+="]"
        _json_subs+="\"$_cat\":{\"count\":$_count,\"files\":$_json_arr}"
    done
    _json_subs+="}"

    _json_exceeded="["
    _efirst=1
    for _e in "${EXCEEDED[@]+"${EXCEEDED[@]}"}"; do
        [[ $_efirst -eq 0 ]] && _json_exceeded+=","
        _efirst=0
        _json_exceeded+="\"$_e\""
    done
    _json_exceeded+="]"

    _json_drift="null"
    [[ -n "$INTENT_DRIFT" ]] && _json_drift="\"$INTENT_DRIFT\""

    echo "{\"state\":\"$STATE\",\"staged_files\":$FILE_COUNT,\"diff_lines\":$DIFF_LINES,\"subsystem_count\":$CATEGORY_COUNT,\"thresholds\":{\"max_files\":$MAX_FILES,\"max_subsystems\":$MAX_SUBSYSTEMS,\"max_diff_lines\":$MAX_DIFF_LINES},\"subsystems\":$_json_subs,\"exceeded\":$_json_exceeded,\"intent_drift\":$_json_drift}"
    exit 0
fi

# Bare state to stdout (always, for backward compatibility)
echo "$STATE"

# Verbose diagnostics to stderr
if [[ "$VERBOSE" -eq 1 ]]; then
    {
        echo "state: $STATE"
        _files_flag=""
        [[ "$FILE_COUNT" -gt "$MAX_FILES" ]] && _files_flag=" (EXCEEDED)"
        echo "staged_files: $FILE_COUNT / max: $MAX_FILES$_files_flag"

        _lines_flag=""
        [[ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]] && _lines_flag=" (EXCEEDED)"
        echo "diff_lines: $DIFF_LINES / max: $MAX_DIFF_LINES$_lines_flag"

        _subs_flag=""
        [[ "$CATEGORY_COUNT" -ge "$MAX_SUBSYSTEMS" ]] && _subs_flag=" (EXCEEDED)"
        echo "subsystems: $CATEGORY_COUNT / max: $MAX_SUBSYSTEMS$_subs_flag"

        for _cat in "${!CATEGORY_FILES[@]}"; do
            _files="${CATEGORY_FILES[$_cat]}"
            _count=$(echo "$_files" | wc -w | tr -d ' ')
            _trimmed=$(echo "$_files" | xargs | sed 's/ /, /g')
            echo "  $_cat ($_count): $_trimmed"
        done

        if [[ ${#EXCEEDED[@]} -gt 0 ]]; then
            echo "exceeded: $(IFS=', '; echo "${EXCEEDED[*]}")"
        fi

        if [[ -n "$INTENT_DRIFT" ]]; then
            echo "intent_drift: $INTENT_DRIFT"
        fi

        if [[ "$USE_CUSTOM_SUBSYSTEMS" -eq 1 ]]; then
            echo "subsystem_source: custom (.claude-atomic.yaml)"
        else
            echo "subsystem_source: generic (built-in)"
        fi
    } >&2
fi
