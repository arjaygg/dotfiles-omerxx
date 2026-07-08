#!/bin/bash
# stack-ship: Fully automated stack branch merge pipeline
# Phase 1: Core merge algorithm with validation and logging

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

  # Check not on main
  if [[ "$branch" == "main" ]]; then
    log_error "Cannot merge main branch — safety check"
    exit 1
  fi

  # Check PR exists
  if ! gh pr view "$branch" >/dev/null 2>&1; then
    log_error "No GitHub PR found for branch: $branch"
    exit 1
  fi
  log_success "PR exists for $branch"

  # Check branch exists locally
  if ! git rev-parse --verify "$branch" >/dev/null 2>&1; then
    log_error "Local branch not found: $branch"
    exit 1
  fi
  log_success "Local branch exists: $branch"
}

# Build dependency graph
build_graph() {
  local target="$1"

  log_info "Building dependency graph..."

  # Find parent branch (first ancestor that is tracked or main)
  local parent="main"
  if git rev-parse "origin/$target" >/dev/null 2>&1; then
    # Use git merge-base to find common ancestor
    parent=$(git merge-base "$target" main)
    # If merge-base is the same as target, parent is main
    if [[ "$parent" == "$(git rev-parse "$target")" ]]; then
      parent="main"
    else
      # Find which tracked branch this merge-base corresponds to
      for branch in $(git branch -r --format='%(refname:short)'); do
        if git rev-parse --verify "$branch" >/dev/null 2>&1; then
          if [[ "$(git rev-parse "$branch")" == "$parent" ]]; then
            parent="${branch#origin/}"
            break
          fi
        fi
      done
    fi
  fi

  log_success "Parent branch: $parent"

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

# Check CI status
check_ci_status() {
  local branch="$1"

  log_info "Checking CI status for $branch..."

  local status=$(gh run list --branch "$branch" --limit 1 --json conclusion --jq '.[0].conclusion' 2>/dev/null || echo "unknown")

  case "$status" in
    success)
      log_success "CI is green"
      return 0
      ;;
    failure)
      log_warning "CI is red — proceeding anyway"
      return 0
      ;;
    *)
      log_warning "CI status unknown (could not fetch)"
      return 0
      ;;
  esac
}

# Merge a single branch
merge_branch() {
  local source_branch="$1"
  local target_branch="$2"

  log_info "Merging $source_branch → $target_branch..."

  local hash_before=$(git rev-parse "$source_branch")

  if [[ $DRY_RUN -eq 0 ]]; then
    # Attempt merge via gh pr merge. --delete-branch conflicts with the
    # worktree-based workflow (git refuses to delete a branch checked out
    # in a worktree), so gh can exit non-zero here even though the PR
    # merge on GitHub already succeeded. Don't trust the exit code alone —
    # verify the real PR state afterward.
    local merge_err
    merge_err=$(gh pr merge "$source_branch" --rebase --delete-branch --auto 2>&1 >/dev/null) || true

    local pr_state
    pr_state=$(gh pr view "$source_branch" --json state -q .state 2>/dev/null || echo "UNKNOWN")

    if [[ "$pr_state" == "MERGED" ]]; then
      local hash_after=$(git rev-parse "$target_branch" 2>/dev/null || echo "$hash_before")

      # Log success
      mkdir -p "$LOG_DIR"
      local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
      local log_entry=$(cat <<EOF
{"timestamp": "$timestamp", "operation": "merge", "branch": "$source_branch", "merged_into": "$target_branch", "hash_before": "$hash_before", "hash_after": "$hash_after", "status": "success", "actor": "$USER"}
EOF
)
      echo "$log_entry" >> "$LOG_FILE"
      log_success "Merged $source_branch → $target_branch"
      if [[ -n "$merge_err" ]]; then
        log_warning "PR merged, but a post-merge step reported: $merge_err"
      fi
      return 0
    else
      log_error "Merge failed for $source_branch (PR state: $pr_state) — manual intervention needed"
      [[ -n "$merge_err" ]] && log_error "$merge_err"
      return 1
    fi
  else
    # Dry-run: just print
    log_info "[dry-run] Would merge $source_branch → $target_branch"
    return 0
  fi
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
  validate_preconditions "$TARGET_BRANCH"
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
  check_ci_status "$TARGET_BRANCH"
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
  read -p "Continue? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Cancelled"
    exit 0
  fi

  # Execute merge
  echo ""
  log_info "Executing merge plan..."
  echo ""

  # Merge main branch
  if merge_branch "$TARGET_BRANCH" "$parent"; then
    log_success "Successfully merged $TARGET_BRANCH → $parent"
  else
    log_error "Merge failed — see above for details"
    exit 1
  fi

  # Merge dependents (if any)
  if [[ -n "$dependents" ]]; then
    echo "$dependents" | while read -r dep; do
      [[ -z "$dep" ]] && continue
      if merge_branch "$dep" "$TARGET_BRANCH"; then
        update_pr_base "$dep" "$TARGET_BRANCH"
      else
        log_warning "Merge of $dep failed — continuing with others"
      fi
    done
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
