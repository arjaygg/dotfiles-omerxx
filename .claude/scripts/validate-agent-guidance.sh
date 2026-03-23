#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
live_root="$HOME/.dotfiles"
global_rules="$repo_root/ai/rules/agent-user-global.md"
configured_global_rules="$live_root/ai/rules/agent-user-global.md"

failures=0

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

require_file() {
  local path="$1"
  if [ -f "$path" ]; then
    pass "found ${path#$repo_root/}"
  else
    fail "missing ${path#$repo_root/}"
  fi
}

require_contains() {
  local path="$1"
  local pattern="$2"
  local label="$3"
  if rg -Fq "$pattern" "$path"; then
    pass "$label"
  else
    fail "$label"
  fi
}

require_symlink_target() {
  local path="$1"
  local expected="$2"
  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    fail "missing $path"
    return
  fi

  local target
  target="$(readlink "$path" 2>/dev/null || true)"
  if [ "$target" = "$expected" ]; then
    pass "$path -> $expected"
  else
    fail "$path expected -> $expected"
  fi
}

require_file "$repo_root/AGENTS.md"
require_file "$global_rules"
require_file "$repo_root/CLAUDE.md"
require_file "$repo_root/.claude/CLAUDE.md"
require_file "$repo_root/.gemini/GEMINI.md"
require_file "$repo_root/.codex/config.toml"
require_file "$repo_root/docs/agent-configuration-architecture.md"

require_contains "$repo_root/CLAUDE.md" "@AGENTS.md" "CLAUDE.md imports AGENTS.md"
require_contains "$repo_root/.claude/CLAUDE.md" "@../ai/rules/agent-user-global.md" ".claude/CLAUDE.md imports global rules (relative path)"
require_contains "$repo_root/.gemini/GEMINI.md" "@../ai/rules/agent-user-global.md" ".gemini/GEMINI.md imports global rules (relative path)"
require_contains "$repo_root/.gemini/settings.json" "\"fileName\": [" ".gemini/settings.json configures context.fileName"
require_contains "$repo_root/.gemini/settings.json" "\"AGENTS.md\"" ".gemini/settings.json includes AGENTS.md"
require_contains "$repo_root/.codex/config.toml" "model_instructions_file = \"~/.dotfiles/ai/rules/agent-user-global.md\"" ".codex/config.toml points to global rules"

if [ "$repo_root" = "$live_root" ]; then
  if [ -d "$HOME/.claude" ] || [ -L "$HOME/.claude" ]; then
    require_symlink_target "$HOME/.claude" "$repo_root/.claude"
  fi
  if [ -e "$HOME/.gemini/GEMINI.md" ] || [ -L "$HOME/.gemini/GEMINI.md" ]; then
    require_symlink_target "$HOME/.gemini/GEMINI.md" "$repo_root/.gemini/GEMINI.md"
  fi
  if [ -e "$HOME/.codex/config.toml" ] || [ -L "$HOME/.codex/config.toml" ]; then
    require_symlink_target "$HOME/.codex/config.toml" "$repo_root/.codex/config.toml"
  fi
else
  pass "skipped live symlink checks in non-live worktree"
fi

if [ "$failures" -ne 0 ]; then
  exit 1
fi
