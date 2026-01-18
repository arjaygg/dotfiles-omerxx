#!/usr/bin/env bash
set -euo pipefail

# End-to-end tests for `.claude/scripts/stack` and underlying pr-stack scripts.
# Runs against a temporary git repo, using stubbed gt/az/jq so it is deterministic.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STACK_CLI="$ROOT_DIR/.claude/scripts/stack"
FIXTURES_BIN="$ROOT_DIR/.claude/scripts/pr-stack/test-fixtures/bin"

say() { printf '%s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

assert_contains() {
  local hay="$1"
  local needle="$2"
  echo "$hay" | grep -Fq "$needle" || fail "Expected output to contain: $needle"
}

assert_file_exists() {
  [ -f "$1" ] || fail "Expected file to exist: $1"
}

require git
require bash
require python3

TMP_ROOT="${TMPDIR:-/tmp}/stack-e2e-$RANDOM-$RANDOM"
cleanup() {
  # Best-effort cleanup; keep it simple and safe.
  if [ -d "$TMP_ROOT/repo" ]; then
    (cd "$TMP_ROOT/repo" && git worktree remove .trees/api >/dev/null 2>&1 || true)
    (cd "$TMP_ROOT/repo" && git worktree remove .trees/ui >/dev/null 2>&1 || true)
    (cd "$TMP_ROOT/repo" && git worktree remove .trees/nwt >/dev/null 2>&1 || true)
  fi
  rm -rf "$TMP_ROOT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p "$TMP_ROOT/repo"

export PATH="$FIXTURES_BIN:$PATH"
export GT_TRUNK="main"
export STACK_E2E="1"

say "== stack e2e: init repo =="
cd "$TMP_ROOT/repo"
git init -q

# Create initial commit on main (avoid global git config changes).
cat > README.md <<'EOF'
test repo for stack e2e
EOF
git add README.md
git -c user.name="stack-e2e" -c user.email="stack-e2e@example.com" commit -qm "init"
git branch -M main

say "== stack e2e: help =="
help_out="$("$STACK_CLI" --help)"
assert_contains "$help_out" "create"
assert_contains "$help_out" "status"
assert_contains "$help_out" "worktree-add"

say "== stack e2e: init charcoal (stubbed gt) =="
"$STACK_CLI" init main >/dev/null
assert_file_exists ".git/.graphite_repo_config"

say "== stack e2e: create stacked worktrees =="
"$STACK_CLI" create "feature/api" main --worktree >/dev/null
"$STACK_CLI" create "feature/ui" "feature/api" --worktree >/dev/null

assert_file_exists ".git/pr-stack-info"
[ -d ".trees/api" ] || fail "Expected .trees/api to exist"
[ -d ".trees/ui" ] || fail "Expected .trees/ui to exist"

say "== stack e2e: status =="
status_out="$("$STACK_CLI" status)"
assert_contains "$status_out" "STACK STATUS"

say "== stack e2e: navigate via eval (worktree-aware up/down) =="
cd ".trees/ui"
eval "$("$STACK_CLI" up)"
pwd_now="$(pwd)"
case "$pwd_now" in
  *"/.trees/api") ;;
  *) fail "Expected eval up to cd into .trees/api, got: $pwd_now" ;;
esac

cd "$TMP_ROOT/repo/.trees/api"
eval "$("$STACK_CLI" down)"
pwd_now="$(pwd)"
case "$pwd_now" in
  *"/.trees/ui") ;;
  *) fail "Expected eval down to cd into .trees/ui, got: $pwd_now" ;;
esac

say "== stack e2e: worktree list/add/remove =="
cd "$TMP_ROOT/repo"
"$STACK_CLI" worktree-list | grep -q ".trees/api" || fail "Expected api worktree listed"

# Create a stacked branch without worktree, then add one.
"$STACK_CLI" create "feature/nwt" main >/dev/null
# `create` without --worktree checks out the new branch in the main worktree.
# Switch back to trunk so we can add a new worktree for feature/nwt.
git checkout -q main
"$STACK_CLI" worktree-add "feature/nwt" >/dev/null
[ -d ".trees/nwt" ] || fail "Expected .trees/nwt to exist"

# Remove the added worktree (must be clean).
"$STACK_CLI" worktree-remove ".trees/nwt" >/dev/null
[ ! -d ".trees/nwt" ] || fail "Expected .trees/nwt to be removed"

say "== stack e2e: doctor/restack/update =="
"$STACK_CLI" doctor >/dev/null || fail "doctor failed"
"$STACK_CLI" restack >/dev/null || fail "restack failed"
"$STACK_CLI" update "feature/api" >/dev/null || fail "update failed"

say "== stack e2e: pr/merge (stubbed az/jq) =="
# Ensure branch exists for create-pr validation
git rev-parse --verify "feature/api" >/dev/null
"$STACK_CLI" pr "feature/api" main "Test PR" --draft >/dev/null || fail "pr failed"
"$STACK_CLI" merge 123 >/dev/null || fail "merge failed"

say "OK: stack e2e passed"

