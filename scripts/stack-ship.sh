#!/usr/bin/env bash
# Compatibility entrypoint; the canonical implementation lives under .claude/scripts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/../.claude/scripts/stack-ship.sh" "$@"
