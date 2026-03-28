#!/bin/bash

BACKEND=$1
SHIFT_COUNT=1

# Default port mappings
GEMINI_PORT=8317
CODEX_PORT=8318
CURSOR_PORT=8319
ROUTER_PORT=8320
AGENT_PORT=8005
STARTUP_TIMEOUT_SECONDS="${CLAUDE_LAUNCH_STARTUP_TIMEOUT:-15}"

# Reuse the local Node CA bundle for Python-based bridges so they can trust the
# same custom corporate/self-signed roots.
if [ -n "$NODE_EXTRA_CA_CERTS" ]; then
    export SSL_CERT_FILE="${SSL_CERT_FILE:-$NODE_EXTRA_CA_CERTS}"
    export REQUESTS_CA_BUNDLE="${REQUESTS_CA_BUNDLE:-$NODE_EXTRA_CA_CERTS}"
fi

function start_proxy() {
    local config=$1
    local port=$2
    if ! is_port_listening "$port"; then
        echo "Starting CLIProxyAPI with $config on port $port..."
        nohup CLIProxyAPI -config ~/.config/cliproxyapi/$config > /tmp/cliproxy-$port.log 2>&1 &
    fi

    if ! wait_for_port "$port" "$STARTUP_TIMEOUT_SECONDS"; then
        echo "ERROR: CLIProxyAPI failed to become ready on port $port within ${STARTUP_TIMEOUT_SECONDS}s." >&2
        if [ -f "/tmp/cliproxy-$port.log" ]; then
            echo "--- tail /tmp/cliproxy-$port.log ---" >&2
            tail -n 60 "/tmp/cliproxy-$port.log" >&2
        fi
        exit 1
    fi
}

function check_status() {
    echo "CLIProxyAPI Status:"
    ps aux | grep CLIProxyAPI | grep -v grep
    echo "Agent-CLI-to-API Status:"
    ps aux | grep agent-cli-to-api | grep -v grep
}

function is_port_listening() {
    local port=$1
    lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1
}

function wait_for_port() {
    local port=$1
    local timeout=$2
    local i
    for ((i=1; i<=timeout; i++)); do
        if is_port_listening "$port"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

function start_agent_bridge() {
    local mode=$1
    local model=$2
    local override=$3

    if [ -n "$override" ] && is_port_listening "$AGENT_PORT"; then
        echo "Restarting agent-cli-to-api for $mode model override..."
        kill "$(lsof -ti :"$AGENT_PORT")" > /dev/null 2>&1 || true
        sleep 1
    fi

    if ! is_port_listening "$AGENT_PORT"; then
        if [ "$mode" = "Gemini" ]; then
            echo "Starting agent-cli-to-api for Gemini..."
            nohup bash -c "cd ~/.local/share/agent-cli-to-api && CODEX_PRESET=gemini-cloudcode GEMINI_MODEL=${model} uv run agent-cli-to-api gemini --port $AGENT_PORT" > /tmp/agent-cli-to-api.log 2>&1 &
        else
            echo "Starting agent-cli-to-api for Cursor Agent..."
            # CURSOR_AGENT_MODEL is a fallback when the request payload has no model.
            # When an explicit --model override is given we set it; otherwise leave empty.
            #
            # CODEX_ALLOW_CLIENT_MODEL_OVERRIDE lets agent-cli-to-api honour the per-request
            # model that CLIProxyAPI writes after applying model-routing rules + alias
            # resolution. Without it, forced CODEX_PROVIDER=cursor-agent causes the gateway
            # to ignore the payload model and default to CURSOR_AGENT_MODEL / "auto".
            local model_env=""
            if [ -n "$override" ]; then
                model_env="$model"
            fi
            
            nohup env \
                CODEX_PROVIDER=cursor-agent \
                CODEX_ALLOW_CLIENT_MODEL_OVERRIDE=1 \
                CURSOR_AGENT_MODEL="${model_env}" \
                CURSOR_AGENT_DISABLE_INDEXING=1 \
                CURSOR_AGENT_EXTRA_ARGS="${CURSOR_AGENT_EXTRA_ARGS:---endpoint https://api2.cursor.sh --http-version 2}" \
                bash -lc "cd ~/.local/share/agent-cli-to-api && uv run agent-cli-to-api cursor-agent --port $AGENT_PORT" \
                > /tmp/agent-cli-to-api.log 2>&1 &
        fi
    fi

    if ! wait_for_port "$AGENT_PORT" "$STARTUP_TIMEOUT_SECONDS"; then
        echo "ERROR: agent-cli-to-api failed to become ready on port $AGENT_PORT within ${STARTUP_TIMEOUT_SECONDS}s." >&2
        if [ -f "/tmp/agent-cli-to-api.log" ]; then
            echo "--- tail /tmp/agent-cli-to-api.log ---" >&2
            tail -n 60 /tmp/agent-cli-to-api.log >&2
        fi
        exit 1
    fi
}

function normalize_model_override() {
    case "$1" in
        gemini-3.1-pro-preview|gemini-pro-preview|pro)
            echo "claude-3-7-sonnet-20250219"
            ;;
        gemini-3-flash-preview|gemini-flash-preview|flash)
            echo "claude-3-5-sonnet-20241022"
            ;;
        "Opus 4.5 Thinking"|opus-thinking|opus)
            echo "claude-3-opus-20240229"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

function gemini_model_for_override() {
    case "$1" in
        claude-3-7-sonnet-20250219|gemini-3.1-pro-preview|gemini-pro-preview|pro)
            echo "gemini-3.1-pro-preview"
            ;;
        claude-3-5-sonnet-20241022|gemini-3-flash-preview|gemini-flash-preview|flash)
            echo "gemini-3-flash-preview"
            ;;
        *)
            echo ""
            ;;
    esac
}

function cursor_model_for_override() {
    case "$1" in
        claude-3-7-sonnet-20250219|gemini-3.1-pro-preview|gemini-3.1-pro|gemini-pro-preview|pro)
            echo "gemini-3.1-pro"
            ;;
        claude-3-5-sonnet-20241022|gemini-3-flash-preview|gemini-3-flash|gemini-flash-preview|flash)
            echo "gemini-3-flash"
            ;;
        claude-3-opus-20240229|"Opus 4.5 Thinking"|opus-thinking|opus)
            echo "Opus 4.5 Thinking"
            ;;
        *)
            echo ""
            ;;
    esac
}

function backend_model_for_client_model() {
    local backend=$1
    local client_model=$2

    case "$backend" in
        gemini)
            case "$client_model" in
                claude-sonnet-4-6|claude-3-7-sonnet-20250219)
                    echo "gemini-2.0-pro-exp-02-05"
                    ;;
                claude-3-5-sonnet-20241022|claude-3-5-haiku-20241022)
                    echo "gemini-2.0-flash-exp"
                    ;;
                *)
                    echo "$client_model"
                    ;;
            esac
            ;;
        codex)
            case "$client_model" in
                claude-sonnet-4-6)
                    echo "gpt-5"
                    ;;
                claude-3-7-sonnet-20250219)
                    echo "gpt-5.4"
                    ;;
                claude-3-5-sonnet-20241022|claude-3-5-haiku-20241022)
                    echo "gpt-5-codex-mini"
                    ;;
                *)
                    echo "$client_model"
                    ;;
            esac
            ;;
        cursor)
            case "$client_model" in
                claude-sonnet-4-6|claude-3-7-sonnet-20250219)
                    echo "gemini-3.1-pro"
                    ;;
                claude-3-5-sonnet-20241022|claude-3-5-haiku-20241022)
                    echo "gemini-3-flash"
                    ;;
                *)
                    echo "$client_model"
                    ;;
            esac
            ;;
        router)
            case "$client_model" in
                claude-sonnet-4-6|claude-3-7-sonnet-20250219|claude-3-5-sonnet-20241022)
                    echo "gemini-3.1-pro-preview"
                    ;;
                *)
                    echo "$client_model"
                    ;;
            esac
            ;;
        *)
            echo "$client_model"
            ;;
    esac
}

function export_statusline_metadata() {
    local backend=$1
    local client_model=$2
    local backend_model=""

    if [ -n "$client_model" ]; then
        backend_model="$(backend_model_for_client_model "$backend" "$client_model")"
    fi

    export CLAUDE_STATUSLINE_BACKEND="$backend"
    export CLAUDE_STATUSLINE_CLIENT_MODEL="$client_model"
    export CLAUDE_STATUSLINE_BACKEND_MODEL="$backend_model"
}

STATUSLINE_BACKEND_MODE="native"

MODEL_OVERRIDE_RAW=""
for ((i=2; i<=$#; i++)); do
    arg="${!i}"
    case "$arg" in
        --model)
            next_index=$((i + 1))
            if [ "$next_index" -le "$#" ]; then
                MODEL_OVERRIDE_RAW="${!next_index}"
            fi
            break
            ;;
        --model=*)
            MODEL_OVERRIDE_RAW="${arg#--model=}"
            break
            ;;
    esac
done

CLAUDE_CODE_MODEL_OVERRIDE=""
GEMINI_MODEL_OVERRIDE=""
CURSOR_MODEL_OVERRIDE=""
if [ -n "$MODEL_OVERRIDE_RAW" ]; then
    CLAUDE_CODE_MODEL_OVERRIDE="$(normalize_model_override "$MODEL_OVERRIDE_RAW")"
    GEMINI_MODEL_OVERRIDE="$(gemini_model_for_override "$MODEL_OVERRIDE_RAW")"
    CURSOR_MODEL_OVERRIDE="$(cursor_model_for_override "$MODEL_OVERRIDE_RAW")"
fi

case $BACKEND in
    router)
        STATUSLINE_BACKEND_MODE="router"
        start_proxy master.yaml "$ROUTER_PORT"
        start_agent_bridge "Gemini" "${GEMINI_MODEL_OVERRIDE:-${GEMINI_MODEL:-gemini-3.1-pro-preview}}" "$GEMINI_MODEL_OVERRIDE"
        export ANTHROPIC_BASE_URL="http://127.0.0.1:$ROUTER_PORT"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        export CLAUDE_CODE_MODEL="claude-sonnet-4-6"
        ;;

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
        STATUSLINE_BACKEND_MODE="gemini"
        start_proxy gemini.yaml $GEMINI_PORT
        export ANTHROPIC_BASE_URL="http://127.0.0.1:$GEMINI_PORT"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        export CLAUDE_CODE_MODEL="claude-3-5-sonnet-20241022"
        ;;
    codex)
        STATUSLINE_BACKEND_MODE="codex"
        start_proxy codex.yaml $CODEX_PORT
        export ANTHROPIC_BASE_URL="http://127.0.0.1:$CODEX_PORT"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        export CLAUDE_CODE_MODEL="claude-sonnet-4-6"
        ;;
    cursor)
        STATUSLINE_BACKEND_MODE="cursor"
        start_agent_bridge "Cursor" "${CURSOR_MODEL_OVERRIDE:-${CURSOR_AGENT_MODEL:-gemini-3.1-pro}}" "$CURSOR_MODEL_OVERRIDE"
        start_proxy cursor.yaml $CURSOR_PORT
        export ANTHROPIC_BASE_URL="http://127.0.0.1:$CURSOR_PORT"
        export ANTHROPIC_AUTH_TOKEN="sk-cliproxyapi-default-key"
        export CLAUDE_CODE_MODEL="claude-3-7-sonnet-20250219"
        ;;
    native)
        unset ANTHROPIC_BASE_URL
        unset ANTHROPIC_AUTH_TOKEN
        unset ANTHROPIC_API_KEY
        unset CLAUDE_CODE_MODEL
        unset CLAUDE_STATUSLINE_BACKEND
        unset CLAUDE_STATUSLINE_CLIENT_MODEL
        unset CLAUDE_STATUSLINE_BACKEND_MODEL
        ;;
    *)
        # If no backend specified, use native or default to first arg as claude command
        unset ANTHROPIC_BASE_URL
        unset ANTHROPIC_AUTH_TOKEN
        unset ANTHROPIC_API_KEY
        unset CLAUDE_CODE_MODEL
        unset CLAUDE_STATUSLINE_BACKEND
        unset CLAUDE_STATUSLINE_CLIENT_MODEL
        unset CLAUDE_STATUSLINE_BACKEND_MODEL
        SHIFT_COUNT=0
        ;;
esac

shift $SHIFT_COUNT
CLAUDE_ARGS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --model)
            if [ -z "$2" ]; then
                echo "Missing value for --model" >&2
                exit 1
            fi
            CLAUDE_CODE_MODEL_OVERRIDE="$(normalize_model_override "$2")"
            shift 2
            ;;
        --model=*)
            CLAUDE_CODE_MODEL_OVERRIDE="$(normalize_model_override "${1#--model=}")"
            shift
            ;;
        *)
            CLAUDE_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ -n "$CLAUDE_CODE_MODEL_OVERRIDE" ]; then
    CLAUDE_CODE_MODEL="$CLAUDE_CODE_MODEL_OVERRIDE"
fi

if [ -n "$CLAUDE_CODE_MODEL" ] && [ "$STATUSLINE_BACKEND_MODE" != "native" ]; then
    export_statusline_metadata "$STATUSLINE_BACKEND_MODE" "$CLAUDE_CODE_MODEL"
fi

if [ -n "$CLAUDE_CODE_MODEL" ]; then
    exec claude --model "$CLAUDE_CODE_MODEL" "${CLAUDE_ARGS[@]}"
else
    exec claude "${CLAUDE_ARGS[@]}"
fi
