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

# --project-from-cwd walks up looking for .serena/project.yml or .git and will settle on
# $HOME if either ever exists there. Serena writes ~/.serena/project.yml whenever it is
# started from $HOME, so this happens by accident and then applies to every cwd that is not
# inside a git repo. Activating $HOME makes Serena index the whole home directory, which
# exceeds tool_timeout and surfaces to the client as an MCP hang. Drop the flag in that case
# so Serena starts with no project instead.
serena_project_root() {
    local dir
    dir="$(pwd -P)"
    while :; do
        if [[ -f "$dir/.serena/project.yml" || -e "$dir/.git" ]]; then
            printf '%s\n' "$dir"
            return 0
        fi
        [[ "$dir" == "/" ]] && return 1
        dir="$(dirname "$dir")"
    done
}

args=()
for arg in "$@"; do
    if [[ "$arg" == "--project-from-cwd" && "$(serena_project_root || true)" == "$HOME" ]]; then
        echo "serena_wrapper: refusing --project-from-cwd; it resolves to \$HOME from $(pwd -P). Starting with no project." >&2
        continue
    fi
    args+=("$arg")
done

exec "$serena_bin" start-mcp-server "${args[@]}"
