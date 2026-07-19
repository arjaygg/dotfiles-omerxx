#!/bin/bash
# Serena MCP stdio wrapper
# Redirect stderr to a log file to keep stdout clean for MCP JSON communication.
# Suppresses Python warnings to reduce noise.
export LOG_LEVEL=ERROR
export PYTHONWARNINGS=ignore
exec uvx --python 3.12 --from git+https://github.com/oraios/serena serena start-mcp-server "$@" 2>> "$HOME/.serena/mcp_stderr.log"
