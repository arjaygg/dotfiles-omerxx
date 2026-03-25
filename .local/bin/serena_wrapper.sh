#!/bin/bash
# Serena MCP stdio wrapper
# Redirects stderr to a log file to keep stdout clean for MCP JSON communication.
# Suppresses Python warnings to reduce noise.
export LOG_LEVEL=ERROR
export PYTHONWARNINGS=ignore
exec serena start-mcp-server "$@" 2>> "$HOME/.serena/mcp_stderr.log"
