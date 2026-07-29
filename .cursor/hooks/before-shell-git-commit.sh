#!/bin/bash
# Cursor beforeShellExecution: gate raw `git commit` in hyper-atomic repos.
# Reads JSON on stdin (Cursor hook protocol). Not a commit-message validator;
# validation runs in git commit-msg via ~/.config/agent-hooks/lib/commit-msg-validate.sh
set -euo pipefail

input="$(cat)"

# Two bugs lived here, and together they made this gate fail OPEN — it allowed every raw
# `git commit`, which is the exact opposite of its purpose. Verified by feeding it a payload that
# should be denied: it raised JSONDecodeError and fell through to the allow at the end.
#
# 1. `python3 - <<'PY'` takes the PROGRAM from stdin, so the heredoc overrode the piped JSON and
#    `json.load(sys.stdin)` was reading the Python source, not the payload (shellcheck SC2259).
#    The payload now arrives via the environment, leaving stdin free for the program.
# 2. `read -r command cwd` reads ONE line and splits it on IFS, so `command` got the first word and
#    `cwd` got the remainder of line 1 — line 2 was never read. Two sequential reads fix that, and
#    a bare `read -r var` takes the whole line, so commands containing spaces survive intact.
{
  read -r command
  read -r cwd
} < <(
  AGENT_HOOK_INPUT="$input" /usr/bin/env python3 <<'PY'
import json
import os

try:
    data = json.loads(os.environ.get("AGENT_HOOK_INPUT") or "{}")
except json.JSONDecodeError:
    # Deliberately allow-by-omission, not fail-closed: with no parseable command there is nothing
    # to match against, so the gate emits blanks and the caller ends at its default `allow`.
    # Denying on a parse error would block every shell command Cursor runs, which is far worse than
    # missing one commit. The protocol should never send malformed JSON; if it does, that is a
    # Cursor bug to fix upstream rather than something to absorb by disabling the shell.
    data = {}

print(data.get("command") or "")
print(data.get("cwd") or "")
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
