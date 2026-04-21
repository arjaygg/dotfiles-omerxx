#!/usr/bin/env bash
# Shared commit-message validation for git commit-msg hooks (and any agent that
# can pass a message file path). Single source of truth for:
# - Conventional commit subject (aligned with ~/.dotfiles/scripts/ai/commit.sh)
# - Non-empty body explaining "why" (from former enforce-commit-body.sh)
#
# Usage: commit-msg-validate.sh <path-to-commit-message-file>
set -euo pipefail

COMMIT_MSG_FILE="${1:-}"
if [[ -z "$COMMIT_MSG_FILE" || ! -f "$COMMIT_MSG_FILE" ]]; then
  echo "⛔ commit-msg-validate: missing or invalid message file" >&2
  exit 1
fi

SUBJECT_LINE="$(head -n 1 "$COMMIT_MSG_FILE")"

# --- Conventional subject (match commit.sh) ---
CONVENTIONAL_PATTERN='^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\([a-zA-Z0-9_/-]+\))?: .+'
if ! printf '%s' "$SUBJECT_LINE" | grep -qE "$CONVENTIONAL_PATTERN"; then
  echo "⛔ Commit subject must follow conventional commit format:" >&2
  echo "   type(scope): description" >&2
  echo "   Types: feat fix docs style refactor test chore build ci perf revert" >&2
  echo "   Got: ${SUBJECT_LINE}" >&2
  exit 1
fi

# --- Body: subject + blank line + body (minimal two-paragraph structure) ---
if ! perl -0777 -ne 'exit 1 unless /^.+\n\n.+/s' "$COMMIT_MSG_FILE"; then
  echo "⛔ Commit message MUST include a body explaining the 'WHY' (intent)." >&2
  echo "" >&2
  echo "Example:" >&2
  echo "  feat(zsh): add fzf history search" >&2
  echo "" >&2
  echo "  Speeds up command recall during pairing sessions." >&2
  exit 1
fi

BODY=$(sed -n '/^$/,$ p' "$COMMIT_MSG_FILE" | sed '1d' | grep -v '^Co-authored-by:' | grep -v '^Signed-off-by:' | tr -d '[:space:]')
if [[ ${#BODY} -lt 10 ]]; then
  echo "⛔ Commit body is too short (${#BODY} chars, min 10)." >&2
  echo "   Write a meaningful explanation of WHY this change is needed." >&2
  exit 1
fi

exit 0
