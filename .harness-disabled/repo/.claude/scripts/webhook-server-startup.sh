#!/bin/bash
# Webhook Server Startup Script
# Start the cicd-monitor webhook server on system boot or manual invocation
#
# Usage:
#   ./webhook-server-startup.sh start     # Start server
#   ./webhook-server-startup.sh stop      # Stop server
#   ./webhook-server-startup.sh status    # Check status
#   ./webhook-server-startup.sh restart   # Restart server
#
# For system boot integration, add to crontab:
#   @reboot /Users/axos-agallentes/.dotfiles/.claude/agents/webhook-server-startup.sh start

set -e

SERVER_SCRIPT="/Users/axos-agallentes/.dotfiles/.claude/agents/webhook-server.py"
PID_FILE="/tmp/cicd-monitor.pid"
LOG_FILE="/tmp/cicd-monitor.log"
PORT=5000

action="${1:-status}"

start_server() {
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "⚠️  Server already running (PID: $(cat "$PID_FILE"))"
        return 1
    fi

    echo "🚀 Starting webhook server..."
    nohup python3 -u "$SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"

    # Wait for server to start
    sleep 2

    if kill -0 "$PID" 2>/dev/null; then
        echo "✓ Server started (PID: $PID)"
        echo "  Listening on: http://0.0.0.0:$PORT"
        echo "  Log file: $LOG_FILE"
        return 0
    else
        echo "✗ Failed to start server. Check log:"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

stop_server() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "✓ Server not running (no PID file)"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "⏹️  Stopping server (PID: $PID)..."
        kill "$PID"
        sleep 1

        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID"
            echo "⚠️  Force-killed server"
        else
            echo "✓ Server stopped"
        fi
    fi

    rm -f "$PID_FILE"
}

check_status() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "❌ Server not running (no PID file)"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ Server running (PID: $PID)"

        # Try health check
        if timeout 2 curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
            echo "✓ Health check passed"
            return 0
        else
            echo "⚠️  Health check failed (might still be starting)"
            return 1
        fi
    else
        echo "❌ Server not responding (PID: $PID)"
        rm -f "$PID_FILE"
        return 1
    fi
}

case "$action" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
