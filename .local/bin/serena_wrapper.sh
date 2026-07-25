#!/bin/bash
# Serena MCP stdio wrapper
# Redirect stderr to a log file to keep stdout clean for MCP JSON communication.
# Suppresses Python warnings to reduce noise.
export LOG_LEVEL=ERROR
export PYTHONWARNINGS=ignore
exec /Users/axos-agallentes/.local/bin/serena start-mcp-server "$@" 2>> "$HOME/.serena/mcp_stderr.log"
