#!/usr/bin/env bash
set -euo pipefail

# Keep MCP launchers independent of the shell's PATH. Prefer user-local
# installs, while retaining Cargo as a compatibility fallback.
candidate="${PCTX_BIN:-}"
if [[ -n "$candidate" && -x "$candidate" ]]; then
    exec "$candidate" "$@"
fi

for candidate in "$HOME/.local/bin/pctx" "$HOME/.cargo/bin/pctx"; do
    if [[ -x "$candidate" && "$candidate" != "$0" ]]; then
        exec "$candidate" "$@"
    fi
done

candidate="$(command -v pctx 2>/dev/null || true)"
if [[ -n "$candidate" && -x "$candidate" && "$candidate" != "$0" ]]; then
    exec "$candidate" "$@"
fi

echo "pctx_wrapper: pctx is not installed (checked \\$HOME/.local/bin and \\$HOME/.cargo/bin)" >&2
exit 127
