#!/usr/bin/env bash
set -euo pipefail

# LeanCtx 3.9.12's CLI prints one extra trailing newline for `read -m
# raw|full`, breaking byte-fidelity verification. Keep the workaround inside
# the LeanCtx launcher so exact reads remain explicit and no second compressor
# is introduced. MCP traffic still delegates unchanged.
if [[ "${1:-}" == "read" ]]; then
    exact_mode=""
    read_path=""
    arguments=("$@")
    for ((index = 1; index < ${#arguments[@]}; index++)); do
        argument="${arguments[$index]}"
        case "$argument" in
            -m|--mode)
                if ((index + 1 < ${#arguments[@]})); then
                    ((index += 1))
                    exact_mode="${arguments[$index]}"
                fi
                ;;
            --mode=*)
                exact_mode="${argument#--mode=}"
                ;;
            --)
                if ((index + 1 < ${#arguments[@]})); then
                    ((index += 1))
                    read_path="${arguments[$index]}"
                fi
                break
                ;;
            -*)
                ;;
            *)
                if [[ -z "$read_path" ]]; then
                    read_path="$argument"
                fi
                ;;
        esac
    done
    if [[ -n "$read_path" && ("$exact_mode" == "raw" || "$exact_mode" == "full") ]]; then
        exec /usr/bin/env python3 -c \
            'from pathlib import Path; import sys; sys.stdout.buffer.write(Path(sys.argv[1]).expanduser().read_bytes())' \
            "$read_path"
    fi
fi

candidate="${LEAN_CTX_BIN:-}"
if [[ -n "$candidate" && -x "$candidate" ]]; then
    exec "$candidate" "$@"
fi

for candidate in "$HOME/.local/bin/lean-ctx" "$HOME/.cargo/bin/lean-ctx"; do
    if [[ -x "$candidate" && "$candidate" != "$0" ]]; then
        exec "$candidate" "$@"
    fi
done

candidate="$(command -v lean-ctx 2>/dev/null || true)"
if [[ -n "$candidate" && -x "$candidate" && "$candidate" != "$0" ]]; then
    exec "$candidate" "$@"
fi

echo "lean_ctx_wrapper: lean-ctx is not installed" >&2
exit 127
