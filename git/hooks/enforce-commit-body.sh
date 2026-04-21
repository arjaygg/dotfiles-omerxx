#!/usr/bin/env bash
# Delegates to shared validation (single source of truth, tracked in this repo).
set -euo pipefail
_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${_HERE}/lib/commit-msg-validate.sh" "$1"
