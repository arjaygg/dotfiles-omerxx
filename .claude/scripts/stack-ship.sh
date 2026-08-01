#!/bin/bash
# stack-ship: Confirmation-gated stack branch merge pipeline
# Validates exact PR state, head, and checks before server-side auto-merge.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=0
TARGET_BRANCH=""
LOG_DIR=".stack-ship"
LOG_FILE="$LOG_DIR/log.jsonl"

# --yes exists because the confirmation below is a bare `read -p`, which blocks forever with no
# TTY. That made every non-interactive caller hang: `auto-ship`, cron, and any agent run. Found by
# hanging on it (plans/2026-07-28-harness-end-to-end-proof.md records the session).
#
# It is NOT a convenience flag, and `auto-ship` must never pass it. The prompt IS the A2 checkpoint
# for an irreversible action: Part VIII caps auto_ship/auto_clean at A2 = "human approves at planned
# checkpoints", so bypassing the prompt unattended would put the leg above its own cap. --yes is for
# a run a human has ALREADY authorised out-of-band, which is why it demands --reason and records it
# in the audit log — a bypass must never be anonymous.
ASSUME_YES=0
YES_REASON=""

# Helper functions
# NOTE: log_* helpers write to stderr, not stdout. Several functions below
# (e.g. build_graph) call these for progress output while also returning
# data via stdout/command substitution; if logs went to stdout they'd get
# interleaved into the captured data.
log_info() {
  echo -e "${BLUE}ℹ${NC} $*" >&2
}

log_success() {
  echo -e "${GREEN}✅${NC} $*" >&2
}

log_error() {
  echo -e "${RED}❌${NC} $*" >&2
}

log_warning() {
  echo -e "${YELLOW}⚠️${NC}  $*" >&2
}

# Parse arguments
parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --dry-run)
        DRY_RUN=1
        log_info "Dry-run mode enabled"
        shift
        ;;
      --branch)
        TARGET_BRANCH="$2"
        shift 2
        ;;
      --yes|-y)
        ASSUME_YES=1
        shift
        ;;
      --reason)
        YES_REASON="$2"
        shift 2
        ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  done
}

# Validate preconditions
validate_preconditions() {
  local branch="$1"

  log_info "Validating preconditions..."

  if [[ "$branch" == "main" ]]; then
    log_error "Cannot merge main branch — safety check"
    return 1
  fi

  if ! git rev-parse --verify "refs/heads/$branch" >/dev/null 2>&1; then
    log_error "Local branch not found: $branch"
    return 1
  fi

  local local_head
  local_head=$(git rev-parse "refs/heads/$branch")

  local pr_json
  if ! pr_json=$(gh pr view "$branch" \
    --json state,isDraft,mergeable,mergeStateStatus,headRefOid,baseRefName 2>/dev/null); then
    log_error "No GitHub PR found for branch: $branch"
    return 1
  fi
  if ! printf '%s' "$pr_json" | jq -e 'type == "object"' >/dev/null 2>&1; then
    log_error "Could not verify PR metadata for $branch"
    return 1
  fi

  local pr_state is_draft mergeable merge_state pr_head
  pr_state=$(printf '%s' "$pr_json" | jq -r '.state // "UNKNOWN"')
  is_draft=$(printf '%s' "$pr_json" | jq -r 'if has("isDraft") then .isDraft else true end')
  mergeable=$(printf '%s' "$pr_json" | jq -r '.mergeable // "UNKNOWN"')
  merge_state=$(printf '%s' "$pr_json" | jq -r '.mergeStateStatus // "UNKNOWN"')
  pr_head=$(printf '%s' "$pr_json" | jq -r '.headRefOid // ""')

  if [[ "$pr_state" != "OPEN" ]]; then
    log_error "PR for $branch is not open (state: $pr_state)"
    return 1
  fi
  if [[ "$is_draft" != "false" ]]; then
    log_error "PR for $branch is a draft"
    return 1
  fi
  if [[ "$mergeable" != "MERGEABLE" || "$merge_state" == "DIRTY" ]]; then
    log_error "PR for $branch is conflicting or has unknown mergeability (mergeable: $mergeable, state: $merge_state)"
    return 1
  fi
  if [[ -z "$pr_head" || "$pr_head" != "$local_head" ]]; then
    log_error "PR head for $branch does not exactly match local branch head"
    log_error "PR: ${pr_head:-missing}; local: $local_head"
    return 1
  fi

  log_success "PR metadata and exact head OID verified for $branch"
}

# Build dependency graph
build_graph() {
  local target="$1"

  log_info "Building dependency graph..."

  # The merge target is whatever the PR says its base is — `gh pr merge` takes no --base, so the
  # PR is the authority. Ask it directly.
  #
  # The previous implementation guessed: it took `git merge-base "$target" main`, then scanned every
  # remote ref for one whose SHA matched, and used that name. That reported "Parent branch: origin"
  # and printed a merge plan reading "→ origin" for a PR whose base was `main`. Harmless to the merge
  # itself, but a dry-run exists precisely to show the plan before an irreversible action, so a
  # mislabelled target defeats the check it is there to provide.
  local parent
  parent=$(gh pr view "$target" --json baseRefName -q .baseRefName 2>/dev/null || echo "")
  if [[ -z "$parent" || "$parent" == "null" ]]; then
    parent="main"
    log_warning "Could not read the PR base for '$target'; assuming '$parent'"
  fi

  log_success "Parent branch: $parent (from the PR base — this is the real merge target)"

  # Find dependents: branches that have $target as ancestor
  local dependents=""
  while IFS= read -r branch; do
    if [[ -z "$branch" ]]; then continue; fi
    if [[ "$branch" == "$target" ]]; then continue; fi
    if git merge-base --is-ancestor "$target" "$branch" 2>/dev/null; then
      dependents="$dependents$branch"$'\n'
    fi
  done < <(git branch --format='%(refname:short)')

  echo "$parent"
  echo "$dependents"
}

# Check required and reported PR checks. Every unrecognized state fails closed.
check_ci_status() {
  local branch="$1"

  log_info "Checking required and reported checks for $branch..."

  local required_json required_rc
  required_rc=0
  required_json=$(gh pr checks "$branch" --required --json name,bucket,state 2>/dev/null) || required_rc=$?
  if ! printf '%s' "$required_json" | jq -e 'type == "array"' >/dev/null 2>&1; then
    log_error "Required-check status is unknown for $branch (gh exit: $required_rc)"
    return 1
  fi
  if [[ "$(printf '%s' "$required_json" | jq 'length')" -eq 0 ]]; then
    log_error "No required checks were reported for $branch"
    return 1
  fi

  local checks_json checks_rc
  checks_rc=0
  checks_json=$(gh pr checks "$branch" --json name,bucket,state 2>/dev/null) || checks_rc=$?
  if ! printf '%s' "$checks_json" | jq -e 'type == "array" and length > 0' >/dev/null 2>&1; then
    log_error "Check status is unknown for $branch (gh exit: $checks_rc)"
    return 1
  fi

  local check_name check_state
  while IFS=$'\t' read -r check_name check_state; do
    [[ -z "$check_name" ]] && check_name="unnamed check"
    check_state=$(printf '%s' "$check_state" | tr '[:upper:]' '[:lower:]')
    case "$check_state" in
      pass|success)
        ;;
      pending|queued|in_progress|expected|waiting|requested)
        log_error "Check is pending for $branch: $check_name ($check_state)"
        return 1
        ;;
      fail|failure|error|cancel|cancelled|timed_out|action_required|startup_failure|stale|skipping|skipped|neutral)
        log_error "Check failed for $branch: $check_name ($check_state)"
        return 1
        ;;
      *)
        log_error "Check status is unknown for $branch: $check_name (${check_state:-missing})"
        return 1
        ;;
    esac
  done < <(printf '%s' "$checks_json" | jq -r '.[] | [(.name // "unnamed check"), (.bucket // .state // "")] | @tsv')

  log_success "All required and reported checks passed for $branch"
}

# Merge a single branch
merge_branch() {
  local source_branch="$1"
  local target_branch="$2"

  log_info "Merging $source_branch → $target_branch..."

  local hash_before
  hash_before=$(git rev-parse "refs/heads/$source_branch")

  if [[ $DRY_RUN -eq 0 ]]; then
    local merge_err
    if ! merge_err=$(gh pr merge "$source_branch" \
      --rebase --auto --match-head-commit "$hash_before" 2>&1); then
      log_error "Merge request failed for $source_branch — no dependent branch will be processed"
      [[ -n "$merge_err" ]] && log_error "$merge_err"
      return 1
    fi

    local pr_state
    pr_state=$(gh pr view "$source_branch" --json state -q .state 2>/dev/null || echo "UNKNOWN")

    if [[ "$pr_state" == "MERGED" ]]; then
      local hash_after
      hash_after=$(git rev-parse "$target_branch" 2>/dev/null || echo "$hash_before")

      mkdir -p "$LOG_DIR"
      local timestamp
      timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
      local confirmed_by="prompt"
      local bypass_reason=""
      if [[ "$ASSUME_YES" == "1" ]]; then
        confirmed_by="--yes"
        bypass_reason="$YES_REASON"
      fi
      local log_entry
      log_entry=$(jq -nc \
        --arg ts "$timestamp" --arg branch "$source_branch" --arg into "$target_branch" \
        --arg hb "$hash_before" --arg ha "$hash_after" --arg actor "${USER:-unknown}" \
        --arg confirmed_by "$confirmed_by" --arg bypass_reason "$bypass_reason" \
        '{timestamp:$ts, operation:"merge", branch:$branch, merged_into:$into, hash_before:$hb, hash_after:$ha, status:"success", actor:$actor, confirmed_by:$confirmed_by, bypass_reason:$bypass_reason}')
      echo "$log_entry" >> "$LOG_FILE"
      log_success "Merged $source_branch → $target_branch"
      return 0
    elif [[ "$pr_state" == "OPEN" ]]; then
      log_success "Server auto-merge enabled for $source_branch; waiting for GitHub to merge it"
      return 2
    fi

    log_error "Merge failed for $source_branch (PR state: $pr_state) — manual intervention needed"
    [[ -n "$merge_err" ]] && log_error "$merge_err"
    return 1
  fi

  log_info "[dry-run] Would merge $source_branch → $target_branch"
  return 0
}

# Update PR base
update_pr_base() {
  local branch="$1"
  local new_base="$2"

  log_info "Updating PR base for $branch to $new_base..."

  if [[ $DRY_RUN -eq 0 ]]; then
    if gh pr edit "$branch" --base "$new_base" 2>/dev/null; then
      log_success "Updated PR base: $branch → $new_base"
      return 0
    else
      log_warning "Could not update PR base for $branch"
      return 1
    fi
  else
    log_info "[dry-run] Would update PR base: $branch → $new_base"
    return 0
  fi
}

# Main execution
main() {
  # Parse arguments
  parse_args "$@"

  # Determine target branch
  if [[ -z "$TARGET_BRANCH" ]]; then
    TARGET_BRANCH=$(git branch --show-current)
  fi

  echo ""
  log_info "Stack Ship — Phase 1 Merge Pipeline"
  echo ""

  # Validate
  validate_preconditions "$TARGET_BRANCH" || exit 1
  echo ""

  # Build graph
  # NOTE: avoid `mapfile` here — it's a bash 4+ builtin, and macOS ships
  # bash 3.2 at /bin/bash regardless of a newer bash on $PATH. Use a
  # portable command-substitution split instead so this works everywhere.
  local graph_output
  graph_output=$(build_graph "$TARGET_BRANCH")
  local parent
  parent=$(printf '%s\n' "$graph_output" | sed -n '1p')
  local dependents
  dependents=$(printf '%s\n' "$graph_output" | sed -n '2,$p' | grep -v '^$' || echo "")

  if [[ -n "$dependents" && "$ASSUME_YES" == "1" && "$DRY_RUN" -eq 0 ]]; then
    log_error "Multi-branch shipment requires the interactive confirmation checkpoint"
    log_error "Refusing unattended stack shipment; run without --yes from a TTY"
    exit 1
  fi

  # Print plan
  if [[ -n "$dependents" ]]; then
    log_info "Dependency tree:"
    echo "  $TARGET_BRANCH (target)"
    echo "$dependents" | sed 's/^/  └─ (dependent) /'
    echo "  ↑"
    echo "  $parent (base)"
  else
    log_info "Dependency tree:"
    echo "  $TARGET_BRANCH (target)"
    echo "  ↑"
    echo "  $parent (base)"
  fi
  echo ""

  # Check CI
  check_ci_status "$TARGET_BRANCH" || exit 1
  echo ""

  # Merge plan
  log_info "Merge Plan:"
  echo "  1. Merge $TARGET_BRANCH → $parent"
  if [[ -n "$dependents" ]]; then
    local step=2
    echo "$dependents" | while read -r dep; do
      [[ -z "$dep" ]] && continue
      echo "  $step. Merge $dep → $TARGET_BRANCH (or rebase)"
      ((step++))
    done
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    echo ""
    log_success "Dry-run complete — no changes made"
    exit 0
  fi

  echo ""
  log_warning "This will execute the merge plan above"
  if [[ "$ASSUME_YES" == "1" ]]; then
    if [[ -z "$YES_REASON" ]]; then
      log_error "--yes requires --reason \"<who authorised this and when>\"."
      log_error "The prompt being bypassed is the A2 checkpoint for an irreversible action, so the"
      log_error "bypass has to be attributable. Re-run with --reason, or drop --yes."
      exit 1
    fi
    log_warning "Confirmation bypassed via --yes: ${YES_REASON}"
  elif [[ ! -t 0 ]]; then
    # Fail loudly instead of blocking forever on a read that nobody can answer. Before this, a
    # non-interactive caller hung indefinitely with the merge plan printed and no indication why.
    log_error "No TTY: the confirmation prompt cannot be answered."
    log_error "For a run a human has already authorised, pass --yes --reason \"<authorisation>\"."
    log_error "auto-ship must NOT do this — the prompt is the A2 checkpoint and auto_ship is capped"
    log_error "at A2 (see ai/rules/agent-user-global.md, Autonomy Tiers)."
    exit 1
  else
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      log_warning "Cancelled"
      exit 0
    fi
  fi

  # Execute merge
  echo ""
  log_info "Executing merge plan..."
  echo ""

  # Merge main branch
  local merge_rc
  merge_rc=0
  merge_branch "$TARGET_BRANCH" "$parent" || merge_rc=$?
  case "$merge_rc" in
    0)
      log_success "Successfully merged $TARGET_BRANCH → $parent"
      ;;
    2)
      log_success "Auto-merge is queued for $TARGET_BRANCH; no dependent branch was processed"
      exit 0
      ;;
    *)
      log_error "Merge failed — see above for details"
      exit 1
      ;;
  esac

  # Merge dependents (interactive multi-branch runs only).
  if [[ -n "$dependents" ]]; then
    while IFS= read -r dep; do
      [[ -z "$dep" ]] && continue
      validate_preconditions "$dep" || exit 1
      check_ci_status "$dep" || exit 1

      local dependent_rc
      dependent_rc=0
      merge_branch "$dep" "$TARGET_BRANCH" || dependent_rc=$?
      case "$dependent_rc" in
        0)
          update_pr_base "$dep" "$TARGET_BRANCH" || exit 1
          ;;
        2)
          log_warning "Auto-merge is queued for $dep; stopping before the next dependent"
          exit 0
          ;;
        *)
          log_error "Merge of $dep failed — stopping the stack immediately"
          exit 1
          ;;
      esac
    done <<< "$dependents"
  fi

  echo ""
  log_success "Stack merge complete!"
  echo ""

  # Show log
  if [[ -f "$LOG_FILE" ]]; then
    log_info "Recent merges:"
    tail -3 "$LOG_FILE" | jq -r '.branch + " → " + .merged_into + " (" + .status + ")"' 2>/dev/null || cat "$LOG_FILE" | tail -3
  fi
}

# Run main
main "$@"
