#!/usr/bin/env bash
# Symbol intent detection — personal preference, user-level hook
# Fires on: "what is X", "explain X", "purpose of X", "how does X"
# Injects a Serena directive so Claude skips grep and goes straight to findSymbol.

set -euo pipefail

HOOK_DATA=$(cat)
USER_INPUT=$(echo "$HOOK_DATA" | jq -r '.prompt // empty')

SYMBOL=$(echo "$USER_INPUT" | sed -nE \
  "s/^[Ww]hat('s| is| does) ([A-Za-z_][A-Za-z0-9_]*).*/\2/p
   s/^[Ee]xplain ([A-Za-z_][A-Za-z0-9_]*).*/\1/p
   s/^[Pp]urpose of ([A-Za-z_][A-Za-z0-9_]*).*/\1/p
   s/^[Hh]ow does ([A-Za-z_][A-Za-z0-9_]*).*/\1/p" | head -1)

if [ -n "$SYMBOL" ]; then
  echo "" >&2
  echo "[SYMBOL LOOKUP] \"$SYMBOL\" → Serena.findSymbol({ name: \"$SYMBOL\" }) first. No grep." >&2
  echo "" >&2
fi
