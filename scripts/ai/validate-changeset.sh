#!/usr/bin/env bash
# validate-changeset.sh — deterministic validation-selection gate for staged changesets.
#
# Plan: plans/2026-07-25-agentic-git-pipeline.md (D2, Step 2).
#
# Classifies each staged file into one of docs | config | source | unknown, driven by the
# `validation:` block in .claude-atomic.yaml (falls back to built-in generic rules if that
# block is absent), then runs the matching validator:
#   docs    -> no extra validation
#   config  -> yq parse (yaml/yml/toml), jq parse (json), or `bash -n` (shell-syntax config
#              files with no structured-data extension, e.g. rc files)
#   source  -> shellcheck (.sh/.bash) or `python3 -m py_compile` (.py); falls back to
#              `bash -n` when the shellcheck binary is not installed
#   unknown -> warn + pass — NEVER blocks. Unrecognized subsystems must not stall the pipeline.
#
# D2 correction: any path under .claude/hooks/ is ALWAYS forced to `source` (shellcheck-
# eligible), regardless of the validation: config — hook-script changes are exactly the case
# where a silent unknown-bucket pass-through would be most dangerous.
#
# Zero network calls. Does not modify commit.sh or any repo file — read-only except for a
# scratch tmp file used to capture validator stderr.
#
# Usage: validate-changeset.sh [--json]
# Exit codes:
#   0 - all staged files passed (unknown-category warnings never affect this)
#   1 - at least one config/source file failed real validation (syntax/lint error)
set -euo pipefail

JSON_MODE=0
for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=1 ;;
    esac
done

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -z "$REPO_ROOT" ]]; then
    echo "validate-changeset.sh: not inside a git repository" >&2
    exit 0
fi

OVERRIDE_FILE="$REPO_ROOT/.claude-atomic.yaml"
TMP_ERR=$(mktemp)
trap 'rm -f "$TMP_ERR"' EXIT

STAGED_FILES=$(cd "$REPO_ROOT" && git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)

declare -a WARNINGS=()
declare -a FAILURES=()
declare -A FILES_BY_CAT

if [[ -z "$STAGED_FILES" ]]; then
    if [[ "$JSON_MODE" -eq 1 ]]; then
        echo '{"result":"pass","categories":{},"warnings":[],"failures":[]}'
    else
        echo "result=pass"
        echo "note=no staged files"
    fi
    exit 0
fi

# --- Parse the validation: block from .claude-atomic.yaml -------------------------------
# Same constrained-YAML convention as atomic-status.sh's subsystems: parser:
#   validation:
#     <category>:
#       - "<pattern>"
# Patterns starting with "*." are extension/suffix matches; everything else is a
# prefix / path-segment match (mirrors categorize_file_custom's semantics).
declare -a VAL_CAT_NAMES=()
declare -a VAL_CAT_PATTERNS=()

if [[ -f "$OVERRIDE_FILE" ]]; then
    in_validation=0
    current_cat=""
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// /}" ]] && continue

        if [[ "$line" =~ ^[A-Za-z] ]]; then
            if [[ "$line" == "validation:" ]]; then
                in_validation=1
                current_cat=""
            else
                in_validation=0
                current_cat=""
            fi
            continue
        fi

        [[ "$in_validation" -eq 0 ]] && continue

        if [[ "$line" =~ ^[[:space:]]{2}[A-Za-z_-]+:[[:space:]]*$ ]]; then
            current_cat=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/:[[:space:]]*$//')
            continue
        fi

        if [[ -n "$current_cat" && "$line" =~ ^[[:space:]]+-[[:space:]] ]]; then
            pattern=$(echo "$line" | sed -e 's/^[[:space:]]*-[[:space:]]*//' -e 's/^"//' -e 's/"$//')
            VAL_CAT_NAMES+=("$current_cat")
            VAL_CAT_PATTERNS+=("$pattern")
        fi
    done < "$OVERRIDE_FILE"
fi

classify_generic() {
    local f="$1"
    case "$f" in
        docs/*|decisions/*|plans/*|goals/*) echo "docs"; return ;;
    esac
    case "$f" in
        *.md|*.txt|*.rst) echo "docs"; return ;;
        *.yaml|*.yml|*.json|*.toml) echo "config"; return ;;
        *.sh|*.bash|*.py) echo "source"; return ;;
    esac
    echo "unknown"
}

classify_custom() {
    local f="$1" i pattern ext
    for i in "${!VAL_CAT_PATTERNS[@]}"; do
        pattern="${VAL_CAT_PATTERNS[$i]}"
        if [[ "$pattern" == \*.* ]]; then
            ext="${pattern#\*}"
            if [[ "$f" == *"$ext" ]]; then
                echo "${VAL_CAT_NAMES[$i]}"
                return
            fi
        else
            if [[ "$f" == "$pattern"* || "$f" == *"/$pattern"* ]]; then
                echo "${VAL_CAT_NAMES[$i]}"
                return
            fi
        fi
    done
    echo "unknown"
}

classify_file() {
    local f="$1"
    # D2 correction: hook scripts are ALWAYS source, regardless of validation: config.
    case "$f" in
        .claude/hooks/*.sh|.claude/hooks/*.bash) echo "source"; return ;;
    esac
    if [[ "${#VAL_CAT_PATTERNS[@]}" -gt 0 ]]; then
        classify_custom "$f"
    else
        classify_generic "$f"
    fi
}

validate_config_file() {
    local f="$1"
    local abspath="$REPO_ROOT/$f"
    [[ ! -f "$abspath" ]] && return 0
    case "$f" in
        *.json)
            if which jq >/dev/null 2>&1; then
                if ! jq empty "$abspath" >/dev/null 2>"$TMP_ERR"; then
                    FAILURES+=("$f: invalid JSON ($(head -1 "$TMP_ERR"))")
                    return 1
                fi
            fi
            ;;
        *.yaml|*.yml|*.toml)
            if which yq >/dev/null 2>&1; then
                if ! yq eval . "$abspath" >/dev/null 2>"$TMP_ERR"; then
                    FAILURES+=("$f: invalid ${f##*.} syntax ($(head -1 "$TMP_ERR"))")
                    return 1
                fi
            fi
            ;;
        *)
            if ! bash -n "$abspath" 2>"$TMP_ERR"; then
                FAILURES+=("$f: bash -n failed ($(head -1 "$TMP_ERR"))")
                return 1
            fi
            ;;
    esac
    return 0
}

validate_source_file() {
    local f="$1"
    local abspath="$REPO_ROOT/$f"
    [[ ! -f "$abspath" ]] && return 0
    case "$f" in
        *.sh|*.bash)
            if which shellcheck >/dev/null 2>&1; then
                if ! shellcheck "$abspath" >"$TMP_ERR" 2>&1; then
                    FAILURES+=("$f: shellcheck found issues ($(head -1 "$TMP_ERR"))")
                    return 1
                fi
            else
                if ! bash -n "$abspath" 2>"$TMP_ERR"; then
                    FAILURES+=("$f: bash -n failed ($(head -1 "$TMP_ERR"))")
                    return 1
                fi
                WARNINGS+=("$f: shellcheck not installed, fell back to bash -n only")
            fi
            ;;
        *.py)
            if which python3 >/dev/null 2>&1; then
                if ! python3 -m py_compile "$abspath" 2>"$TMP_ERR"; then
                    FAILURES+=("$f: python3 -m py_compile failed ($(head -1 "$TMP_ERR"))")
                    return 1
                fi
            fi
            ;;
        *)
            WARNINGS+=("$f: classified as source but no validator configured for this file type")
            ;;
    esac
    return 0
}

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    cat=$(classify_file "$f")
    FILES_BY_CAT["$cat"]="${FILES_BY_CAT[$cat]-}$f"$'\n'
    case "$cat" in
        docs) : ;;
        config) validate_config_file "$f" || true ;;
        source) validate_source_file "$f" || true ;;
        unknown) WARNINGS+=("$f: unrecognized subsystem for validation; passing without checks") ;;
    esac
done <<< "$STAGED_FILES"

RESULT="pass"
[[ "${#FAILURES[@]}" -gt 0 ]] && RESULT="fail"

if [[ "$JSON_MODE" -eq 1 ]]; then
    cat_json="{"
    first=1
    for cat in "${!FILES_BY_CAT[@]}"; do
        [[ "$first" -eq 0 ]] && cat_json+=","
        first=0
        files_json="["
        ffirst=1
        while IFS= read -r f; do
            [[ -z "$f" ]] && continue
            [[ "$ffirst" -eq 0 ]] && files_json+=","
            ffirst=0
            files_json+="\"$(json_escape "$f")\""
        done <<< "${FILES_BY_CAT[$cat]}"
        files_json+="]"
        cat_json+="\"$(json_escape "$cat")\":$files_json"
    done
    cat_json+="}"

    warn_json="["
    first=1
    for w in "${WARNINGS[@]+"${WARNINGS[@]}"}"; do
        [[ "$first" -eq 0 ]] && warn_json+=","
        first=0
        warn_json+="\"$(json_escape "$w")\""
    done
    warn_json+="]"

    fail_json="["
    first=1
    for f in "${FAILURES[@]+"${FAILURES[@]}"}"; do
        [[ "$first" -eq 0 ]] && fail_json+=","
        first=0
        fail_json+="\"$(json_escape "$f")\""
    done
    fail_json+="]"

    echo "{\"result\":\"$RESULT\",\"categories\":$cat_json,\"warnings\":$warn_json,\"failures\":$fail_json}"
else
    echo "result=$RESULT"
    for w in "${WARNINGS[@]+"${WARNINGS[@]}"}"; do
        echo "warning: $w"
    done
    for f in "${FAILURES[@]+"${FAILURES[@]}"}"; do
        echo "failure: $f"
    done
fi

[[ "$RESULT" == "fail" ]] && exit 1
exit 0
