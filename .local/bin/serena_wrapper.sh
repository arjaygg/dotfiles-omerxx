#!/bin/bash
# Serena MCP stdio wrapper
# Redirect stderr to a log file to keep stdout clean for MCP JSON communication.
# Suppresses Python warnings to reduce noise.
export LOG_LEVEL=ERROR
export PYTHONWARNINGS=ignore

mkdir -p "$HOME/.serena"
exec 2>> "$HOME/.serena/mcp_stderr.log"

serena_bin="${SERENA_BIN:-}"
if [[ ! -x "$serena_bin" ]]; then
    if [[ -x "$HOME/.local/bin/serena" ]]; then
        serena_bin="$HOME/.local/bin/serena"
    else
        serena_bin="$(command -v serena 2>/dev/null || true)"
    fi
fi

if [[ -z "$serena_bin" || ! -x "$serena_bin" ]]; then
    echo "serena_wrapper: Serena is not installed; run: uv tool install --from git+https://github.com/oraios/serena serena-agent" >&2
    exit 127
fi

exec "$serena_bin" start-mcp-server "$@"
