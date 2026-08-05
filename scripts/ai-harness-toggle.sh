#!/usr/bin/env bash
set -euo pipefail

ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPO_DISABLED="$ROOT/.harness-disabled"
HOME_DISABLED="$HOME/.ai-harness-disabled"

repo_paths=(
  ".cursor" ".claude" ".gemini" ".codex" ".windsurf" ".claude-global"
  "ai" "AGENTS.md" "CLAUDE.md" ".cursorrules" ".windsurfrules"
  ".mcp.json" ".mcp.example.json"
)

home_paths=(
  ".cursor/commands" ".cursor/hooks" ".cursor/rules" ".cursor/skills"
  ".cursor/output-styles" ".cursor/agents" ".cursor/skills-cursor"
  ".cursor/hooks.json" ".cursor/mcp.example.json" ".cursor/CURSOR_SETUP_GUIDE.md"
  ".cursor/blocklist" ".cursor/Library" ".cursor/rules.md"
  ".claude/agents" ".claude/commands" ".claude/hooks" ".claude/rules"
  ".claude/skills" ".claude/output-styles" ".claude/claude-statusline"
  ".claude/plugins" ".claude/CLAUDE.md" ".claude/settings.json"
  ".claude/settings.local.json"
  ".gemini" ".codex" ".windsurf"
)

move_if_present() {
  local source="$1" target="$2"
  [ -e "$source" ] || [ -L "$source" ] || return 0
  mkdir -p "$(dirname "$target")"
  if [ -e "$target" ] || [ -L "$target" ]; then
    printf 'refusing to overwrite %s\n' "$target" >&2
    exit 1
  fi
  mv "$source" "$target"
}

disable() {
  [ ! -e "$REPO_DISABLED" ] || {
    printf 'AI harness is already disabled at %s\n' "$REPO_DISABLED"
    exit 0
  }

  local stamp backup path
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="$HOME_DISABLED/$stamp"
  mkdir -p "$REPO_DISABLED/repo" "$backup"

  for path in "${repo_paths[@]}"; do
    move_if_present "$ROOT/$path" "$REPO_DISABLED/repo/$path"
  done
  for path in "${home_paths[@]}"; do
    move_if_present "$HOME/$path" "$backup/$path"
  done

  printf '%s\n' "$backup" > "$REPO_DISABLED/home-backup"
  cat > "$REPO_DISABLED/README.txt" <<'EOF'
AI coding-agent harness disabled.

Run scripts/ai-harness-toggle.sh enable to restore the repository files and
the live home-directory links/configuration from the recorded backup.
EOF
  printf 'AI harness disabled. Backup: %s\n' "$backup"
}

enable() {
  [ -e "$REPO_DISABLED" ] || {
    printf 'AI harness is not disabled\n'
    exit 0
  }

  local backup path
  backup="$(<"$REPO_DISABLED/home-backup")"
  [ -d "$backup" ] || {
    printf 'missing home backup: %s\n' "$backup" >&2
    exit 1
  }

  for path in "${repo_paths[@]}"; do
    move_if_present "$REPO_DISABLED/repo/$path" "$ROOT/$path"
  done
  for path in "${home_paths[@]}"; do
    move_if_present "$backup/$path" "$HOME/$path"
  done
  rm -rf "$REPO_DISABLED"
  printf 'AI harness enabled\n'
}

status() {
  if [ -e "$REPO_DISABLED" ]; then
    printf 'disabled\n'
  else
    printf 'enabled\n'
  fi
}

case "${1:-status}" in
  disable) disable ;;
  enable) enable ;;
  status) status ;;
  *)
    printf 'usage: %s {disable|enable|status}\n' "$0" >&2
    exit 2
    ;;
esac
