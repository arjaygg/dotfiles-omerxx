#!/bin/bash

BACKEND=$1
SHIFT_COUNT=1

# Default port mappings
GEMINI_PORT=8317
CODEX_PORT=8318
CURSOR_PORT=8319

function start_proxy() {
    local config=$1
    local port=$2
    if ! lsof -i :$port > /dev/null; then
        echo "Starting CLIProxyAPI with $config on port $port..."
        nohup CLIProxyAPI -config ~/.config/cliproxyapi/$config > /tmp/cliproxy-$port.log 2>&1 &
        sleep 2
    fi
}

function check_status() {
    echo "CLIProxyAPI Status:"
    ps aux | grep CLIProxyAPI | grep -v grep
    echo "Agent-CLI-to-API Status:"
    ps aux | grep agent-cli-to-api | grep -v grep
}

case $BACKEND in
    stop)
        echo "Stopping all proxies..."
        pkill -f CLIProxyAPI
        pkill -f agent-cli-to-api
        exit 0
        ;;

    status)
        check_status
        exit 0
        ;;

    gemini)
        start_proxy gemini.yaml $GEMINI_PORT
        export ANTHROPIC_BASE_URL="http://localhost:$GEMINI_PORT/v1"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        ;;
    codex)
        start_proxy codex.yaml $CODEX_PORT
        export ANTHROPIC_BASE_URL="http://localhost:$CODEX_PORT/v1"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        ;;
    cursor)
        # Start agent-cli-to-api if needed
        if ! lsof -i :8000 > /dev/null; then
            echo "Starting agent-cli-to-api for cursor..."
            nohup bash -c "cd ~/.local/share/agent-cli-to-api && uv run agent-cli-to-api cursor-agent" > /tmp/agent-cli-to-api.log 2>&1 &
            sleep 2
        fi
        start_proxy cursor.yaml $CURSOR_PORT
        export ANTHROPIC_BASE_URL="http://localhost:$CURSOR_PORT/v1"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        ;;
    native)
        unset ANTHROPIC_BASE_URL
        unset ANTHROPIC_AUTH_TOKEN
        ;;
    *)
        # If no backend specified, use native or default to first arg as claude command
        unset ANTHROPIC_BASE_URL
        unset ANTHROPIC_AUTH_TOKEN
        SHIFT_COUNT=0
        ;;
esac

shift $SHIFT_COUNT
exec claude "$@"
