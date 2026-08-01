#!/usr/bin/env bash
# Autonomy tier resolver (plan plans/2026-07-27-native-agent-orchestration.md Part VIII, Step 18).
#
# Reports the A0-A4 autonomy tier actually in force for one pipeline leg. READ-ONLY:
# this script never writes any store, so it can never promote anything. Demotion
# markers are written by .claude/hooks/git-pipeline-gate.sh; the declared ceiling and
# the risk-acceptance override are human-edited in .claude-atomic.yaml.
#
#   effective = min(hard_cap, declared, max(evidence_tier, override_tier))
#               minus 1 if an unhealed demotion marker exists, floored at A0
#
# Three stores, three owners -- the store the gate writes is deliberately NOT
# .claude-atomic.yaml, because D3 (see that file) forbids pipeline-driven edits to it:
#
#   declared ceiling  .claude-atomic.yaml `pipeline:`         human only    tracked
#   risk override     .claude-atomic.yaml `autonomy_override:` human only   tracked
#   demotion marker   <git-common-dir>/autonomy-demoted-<stage>  the gate   untracked
#   eval evidence     evals/reports/<stage>.json               human commit tracked
#
# So the gate can only ever *lower* a tier. Self-escalation is structurally
# impossible rather than policy-forbidden.
#
# NO `trap ... ERR` HERE ON PURPOSE. git-pipeline-gate.sh runs under
# `trap 'exit 0' ERR` so a hook failure can never wedge a session; that posture is
# correct for *availability* but fatal for *authorization* -- under it, a missing or
# malformed store silently reads as "no restrictions". This script therefore fails
# loudly (non-zero) and leaves it to each caller to decide what a failure means.
# Callers must treat a non-zero exit as A0, never as "unrestricted".
#
# Exit codes:
#   0  tier resolved and printed
#   2  usage error
#   3  config error -- legacy boolean value, unparseable tier, or a declared tier
#      above the hard cap for an irreversible leg (fails closed, does not clamp)
#   4  not a git repository / .claude-atomic.yaml absent
#
# Usage:
#   autonomy-tier.sh --stage auto_ship [--json]
#   autonomy-tier.sh --all [--json]

set -euo pipefail

STAGES="auto_stack auto_commit auto_push auto_pr auto_ship auto_clean"

# Irreversible legs. Part VIII: "Irreversible actions never exceed A2 regardless of
# evidence ... Blast radius caps the tier." This table is an invariant, not a tunable
# -- it is the one thing that is deliberately a script literal rather than config, so
# that config cannot raise it.
IRREVERSIBLE="auto_ship auto_clean"
IRREVERSIBLE_CAP=2
DEFAULT_CAP=4

die() { printf 'autonomy-tier: %s\n' "$1" >&2; exit "${2:-2}"; }

tier_num() {
    case "$1" in
        A0) echo 0 ;; A1) echo 1 ;; A2) echo 2 ;; A3) echo 3 ;; A4) echo 4 ;;
        true|false)
            die "legacy boolean '$1' in .claude-atomic.yaml -- migrate the pipeline: block to A0-A4 tiers (plan Step 18). Refusing rather than guessing a tier." 3 ;;
        "") echo "" ;;
        *)  die "unparseable tier '$1' -- expected A0..A4" 3 ;;
    esac
}

tier_str() { printf 'A%s\n' "$1"; }

is_irreversible() {
    case " $IRREVERSIBLE " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Read one key from a named top-level block, returning everything after `key:` with
# any trailing comment stripped. Scoped to the block so `auto_*` keys can never be
# picked up from `subsystems:` or `validation:`.
read_block_key() {
    local block="$1" key="$2"
    awk -v block="$block" -v key="$key" '
        $0 ~ "^" block ":" { inblock = 1; next }
        /^[^[:space:]#]/   { inblock = 0 }
        inblock && $1 == key ":" {
            sub(/^[[:space:]]*[^:]+:[[:space:]]*/, "")
            sub(/[[:space:]]*#.*$/, "")
            gsub(/[[:space:]]+$/, "")
            print; exit
        }
    ' "$ATOMIC_YAML"
}

# --- locate the repo and its shared git dir -------------------------------------
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "not a git repository" 4
# --git-common-dir, NOT --git-dir: from a linked worktree (.trees/<x>/, which is how
# every non-trivial change in this repo is made) --git-dir returns
# .git/worktrees/<name>, so demotion markers would be per-worktree and creating a
# branch would silently launder every demotion.
GIT_COMMON=$(cd "$REPO_ROOT" && cd "$(git rev-parse --git-common-dir)" && pwd) \
    || die "cannot resolve --git-common-dir" 4

ATOMIC_YAML="$REPO_ROOT/.claude-atomic.yaml"
[ -f "$ATOMIC_YAML" ] || die "$ATOMIC_YAML not found" 4

# --- args ------------------------------------------------------------------------
STAGE=""; AS_JSON=0; DO_ALL=0
while [ $# -gt 0 ]; do
    case "$1" in
        --stage) STAGE="${2:-}"; [ -n "$STAGE" ] || die "--stage needs a value"; shift 2 ;;
        --all)   DO_ALL=1; shift ;;
        --json)  AS_JSON=1; shift ;;
        -h|--help) sed -n '43,46p' "$0"; exit 0 ;;
        *) die "unknown argument '$1'" ;;
    esac
done
[ -n "$STAGE" ] || [ "$DO_ALL" = 1 ] || die "one of --stage <name> or --all is required"

if [ -n "$STAGE" ]; then
    case " $STAGES " in
        *" $STAGE "*) : ;;
        *) die "unknown stage '$STAGE' -- expected one of: $STAGES" ;;
    esac
fi

# --- risk-acceptance override (read once) ----------------------------------------
# A dated, signed acceptance of running a leg without eval evidence. Kept in a
# SEPARATE term from evidence_tier on purpose: folding it into evidence would make
# "promotion requires a committed green eval run" (Part VIII) a false statement.
OV_TIER_RAW=$(read_block_key autonomy_override tier || true)
OV_BASIS=$(read_block_key autonomy_override basis || true)
OV_EXPIRES=$(read_block_key autonomy_override expires || true)
OV_STAGES=$(read_block_key autonomy_override stages || true)
OV_SIGNED=$(read_block_key autonomy_override signed_off_by || true)
TODAY=$(date +%F)

override_for() {   # → tier number, or 0 if the override does not apply
    local stage="$1"
    [ -n "$OV_TIER_RAW" ] || { echo 0; return; }
    case " $OV_STAGES " in *" $stage "*) : ;; *) echo 0; return ;; esac
    # Enforced, not decorative: an expired acceptance grants nothing.
    if [ -n "$OV_EXPIRES" ] && [ "$OV_EXPIRES" \< "$TODAY" ]; then echo 0; return; fi
    # An override can never buy autonomy on an irreversible leg.
    if is_irreversible "$stage"; then echo 0; return; fi
    tier_num "$OV_TIER_RAW"
}

override_note_for() {
    local stage="$1"
    [ -n "$OV_TIER_RAW" ] || { echo "none"; return; }
    case " $OV_STAGES " in *" $stage "*) : ;; *) echo "not-listed"; return ;; esac
    if [ -n "$OV_EXPIRES" ] && [ "$OV_EXPIRES" \< "$TODAY" ]; then
        echo "EXPIRED on $OV_EXPIRES"; return
    fi
    if is_irreversible "$stage"; then echo "refused (irreversible leg)"; return; fi
    echo "${OV_BASIS:-unspecified} until ${OV_EXPIRES:-no-expiry}"
}

# --- evidence ---------------------------------------------------------------------
# Promotion requires a *committed* green eval run. `git ls-files --error-unmatch`
# is NOT sufficient -- it succeeds on a merely staged file, so `git add` alone would
# buy a promotion. `git cat-file -e HEAD:<path>` is the real check.
evidence_for() {
    local stage="$1" report="evals/reports/${stage}.json"
    git -C "$REPO_ROOT" cat-file -e "HEAD:${report}" 2>/dev/null || { echo 0; return; }
    local green
    green=$(git -C "$REPO_ROOT" show "HEAD:${report}" 2>/dev/null \
        | jq -r '.green // false' 2>/dev/null) || { echo 0; return; }
    [ "$green" = "true" ] || { echo 0; return; }
    local claimed
    claimed=$(git -C "$REPO_ROOT" show "HEAD:${report}" 2>/dev/null \
        | jq -r '.tier // ""' 2>/dev/null) || { echo 0; return; }
    [ -n "$claimed" ] || { echo 0; return; }
    tier_num "$claimed"
}

# --- demotion ---------------------------------------------------------------------
marker_for() { printf '%s/autonomy-demoted-%s\n' "$GIT_COMMON" "$1"; }

resolve_one() {
    local stage="$1"
    local declared_raw declared cap evidence override effective demoted marker reason

    declared_raw=$(read_block_key pipeline "$stage" || true)
    [ -n "$declared_raw" ] || { declared_raw="A0"; }
    declared=$(tier_num "$declared_raw")

    if is_irreversible "$stage"; then cap=$IRREVERSIBLE_CAP; else cap=$DEFAULT_CAP; fi

    # Fail closed, do not clamp: a declared tier above the cap is a config error the
    # human must fix, not something this script quietly corrects.
    if [ "$declared" -gt "$cap" ]; then
        die "$stage declares $declared_raw but is capped at $(tier_str $cap) (irreversible leg -- Part VIII: blast radius caps the tier). Fix .claude-atomic.yaml." 3
    fi

    evidence=$(evidence_for "$stage")
    override=$(override_for "$stage")

    local floor=$evidence
    [ "$override" -gt "$floor" ] && floor=$override

    effective=$declared
    [ "$cap" -lt "$effective" ] && effective=$cap
    [ "$floor" -lt "$effective" ] && effective=$floor

    marker=$(marker_for "$stage")
    if [ -f "$marker" ]; then
        demoted=true
        effective=$((effective - 1))
        [ "$effective" -lt 0 ] && effective=0
        reason="demoted by $marker (rm it after committing a green eval report)"
    else
        demoted=false
        if [ "$floor" -lt "$declared" ]; then
            reason="capped by evidence/override floor $(tier_str $floor); declared $(tier_str $declared)"
        elif [ "$cap" -lt "$declared" ]; then
            reason="capped at $(tier_str $cap) (irreversible leg)"
        else
            reason="declared tier in force"
        fi
    fi

    if [ "$AS_JSON" = 1 ]; then
        jq -nc \
            --arg stage "$stage" \
            --arg declared "$(tier_str $declared)" \
            --arg hard_cap "$(tier_str $cap)" \
            --arg evidence_tier "$(tier_str $evidence)" \
            --arg override_tier "$(tier_str $override)" \
            --arg override_basis "$(override_note_for "$stage")" \
            --arg effective "$(tier_str $effective)" \
            --arg signed_off_by "${OV_SIGNED:-}" \
            --argjson demoted "$demoted" \
            --arg marker "$marker" \
            --arg reason "$reason" \
            '{stage:$stage, declared:$declared, hard_cap:$hard_cap,
              evidence_tier:$evidence_tier, override_tier:$override_tier,
              override_basis:$override_basis, signed_off_by:$signed_off_by,
              demoted:$demoted, marker:$marker,
              effective:$effective, reason:$reason}'
    else
        printf '%-12s effective=%s  declared=%s cap=%s evidence=%s override=%s (%s)  demoted=%s\n' \
            "$stage" "$(tier_str $effective)" "$(tier_str $declared)" "$(tier_str $cap)" \
            "$(tier_str $evidence)" "$(tier_str $override)" "$(override_note_for "$stage")" "$demoted"
    fi
}

if [ "$DO_ALL" = 1 ]; then
    if [ "$AS_JSON" = 1 ]; then
        printf '['
        first=1
        for s in $STAGES; do
            [ "$first" = 1 ] || printf ','
            first=0
            resolve_one "$s"
        done
        printf ']\n'
    else
        for s in $STAGES; do resolve_one "$s"; done
    fi
else
    resolve_one "$STAGE"
fi
