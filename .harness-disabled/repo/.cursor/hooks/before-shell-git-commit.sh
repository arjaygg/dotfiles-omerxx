#!/bin/bash
# Cursor beforeShellExecution: gate raw `git commit` in hyper-atomic repos.
# Reads JSON on stdin (Cursor hook protocol). Not a commit-message validator;
# validation runs in git commit-msg via ~/.config/agent-hooks/lib/commit-msg-validate.sh
set -euo pipefail

input="$(cat)"
if ! command=$(printf '%s' "$input" | jq -r \
  'if (.command | type) == "string" then .command else "" end' 2>/dev/null); then
  echo '{"permission":"deny","user_message":"Malformed beforeShellExecution payload."}'
  exit 0
fi
cwd=$(printf '%s' "$input" | jq -r \
  'if (.cwd | type) == "string" then .cwd else "" end')

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
