#!/bin/bash
# Cursor beforeShellExecution: gate raw `git commit` in hyper-atomic repos.
# Reads JSON on stdin (Cursor hook protocol). Not a commit-message validator;
# validation runs in git commit-msg via ~/.config/agent-hooks/lib/commit-msg-validate.sh
set -euo pipefail

input="$(cat)"
read -r command cwd < <(
  printf '%s' "$input" | /usr/bin/env python3 - <<'PY'
import json
import sys

data = json.load(sys.stdin)
command = data.get("command") or ""
cwd = data.get("cwd") or ""
print(command)
print(cwd)
PY
)

if [[ -z "$cwd" ]]; then
  cwd="$(pwd)"
fi

if [[ "$command" =~ \.dotfiles/scripts/ai/(commit|checkpoint)\.sh ]]; then
  echo '{ "permission": "allow" }'
  exit 0
fi

if [[ "$command" =~ (^|[[:space:]])git[[:space:]]+commit([[:space:]]|$) ]]; then
  hooks_path="$(git -C "$cwd" config --local core.hooksPath 2>/dev/null || true)"
  if [[ "$hooks_path" == "$HOME/.dotfiles/git/hooks" ]]; then
    cat <<'JSON'
{
  "permission": "deny",
  "user_message": "Use ~/.dotfiles/scripts/ai/commit.sh instead of git commit so conventional commit format and atomic checks run.",
  "agent_message": "Blocked raw git commit in a hyper-atomic repo. Use commit.sh or checkpoint.sh."
}
JSON
    exit 0
  fi
fi

echo '{ "permission": "allow" }'
