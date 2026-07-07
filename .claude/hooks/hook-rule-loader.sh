#!/usr/bin/env bash
# hook-rule-loader.sh — loads declarative rules from hook-config.yaml
#
# Rule format in hook-config.yaml:
#   rule.<name>.action: block|warn|off
#   rule.<name>.pattern: <ERE pattern matched against Bash CMD>
#   rule.<name>.message: <human-readable block/hint message>
#   rule.<name>.tool: <suggested tool (informational)>
#
# Usage (source from a hook):
#   source "$HOME/.dotfiles/.claude/hooks/hook-rule-loader.sh"
#   check_bash_cmd_rules "$CMD"    # exits 1 if blocked, prints hint if warn

HOOK_RULE_CFG="${HOOK_CONFIG:-$HOME/.dotfiles/.claude/hooks/hook-config.yaml}"

# Get a single field for a named rule.
# Usage: get_rule_field <rule-name> <field>
get_rule_field() {
    local rule_name="$1" field="$2"
    [[ ! -f "$HOOK_RULE_CFG" ]] && return 0
    grep "^rule\.${rule_name}\.${field}:" "$HOOK_RULE_CFG" 2>/dev/null \
        | sed 's/^[^:]*: *//' \
        | tr -d '"' \
        | head -1
}

# List all rule names defined in the config.
list_rule_names() {
    [[ ! -f "$HOOK_RULE_CFG" ]] && return 0
    grep '^rule\.' "$HOOK_RULE_CFG" 2>/dev/null \
        | sed 's/^rule\.\([^.]*\)\..*/\1/' \
        | sort -u
}

# Check CMD against all bash rules in hook-config.yaml.
# Calls hook_block() (from hook-metrics.sh) or prints hint.
# Requires hook-metrics.sh to be sourced first for hook_block().
# Returns 0 if no rule matched (caller should exit 0 normally).
check_bash_cmd_rules() {
    local cmd="$1"
    [[ ! -f "$HOOK_RULE_CFG" ]] && return 0

    while IFS= read -r rule_name; do
        local action pattern message tool
        action=$(get_rule_field "$rule_name" "action")
        pattern=$(get_rule_field "$rule_name" "pattern")
        message=$(get_rule_field "$rule_name" "message")
        tool=$(get_rule_field "$rule_name" "tool")

        [[ -z "$action" || "$action" == "off" ]] && continue
        [[ -z "$pattern" ]] && continue

        if echo "$cmd" | grep -qE "$pattern" 2>/dev/null; then
            local full_msg="$message"
            [[ -n "$tool" ]] && full_msg="$message (use: $tool)"
            case "$action" in
                block)
                    # _deny() (pre-tool-gate-v2.sh) emits the JSON permissionDecision
                    # that actually halts the tool; hook_block() is a fallback for
                    # other callers; plain exit 1 does NOT block in Claude Code.
                    if declare -f _deny >/dev/null 2>&1; then
                        _deny "BLOCKED [rule.$rule_name]: $full_msg"
                    elif declare -f hook_block >/dev/null 2>&1; then
                        hook_block "rule.$rule_name" "Bash" "BLOCKED: $full_msg"
                    else
                        echo "BLOCKED: $full_msg"
                        exit 1
                    fi
                    return 1
                    ;;
                warn)
                    echo "HINT [rule.$rule_name]: $full_msg"
                    ;;
            esac
        fi
    done < <(list_rule_names)
    return 0
}

# Check file path against all read-guard rules in hook-config.yaml.
# Rule format:
#   read-guard.<name>.action: block|warn|off
#   read-guard.<name>.path_pattern: <shell glob pattern>
#   read-guard.<name>.message: <message>
check_read_path_rules() {
    local file_path="$1"
    [[ ! -f "$HOOK_RULE_CFG" ]] && return 0

    while IFS= read -r rule_name; do
        local action path_pattern message
        action=$(grep "^read-guard\.${rule_name}\.action:" "$HOOK_RULE_CFG" 2>/dev/null \
            | sed 's/^[^:]*: *//' | tr -d '"' | head -1)
        path_pattern=$(grep "^read-guard\.${rule_name}\.path_pattern:" "$HOOK_RULE_CFG" 2>/dev/null \
            | sed 's/^[^:]*: *//' | tr -d '"' | head -1)
        message=$(grep "^read-guard\.${rule_name}\.message:" "$HOOK_RULE_CFG" 2>/dev/null \
            | sed 's/^[^:]*: *//' | tr -d '"' | head -1)

        [[ -z "$action" || "$action" == "off" ]] && continue
        [[ -z "$path_pattern" ]] && continue

        # Shell glob match using case
        case "$file_path" in
            $path_pattern)
                case "$action" in
                    block)
                        if declare -f _deny >/dev/null 2>&1; then
                            _deny "BLOCKED [read-guard.$rule_name]: $message"
                        elif declare -f hook_block >/dev/null 2>&1; then
                            hook_block "read-guard.$rule_name" "Read" "BLOCKED: $message"
                        else
                            echo "BLOCKED: $message"
                            exit 1
                        fi
                        return 1
                        ;;
                    warn)
                        echo "HINT [read-guard.$rule_name]: $message"
                        ;;
                esac
                ;;
        esac
    done < <(grep '^read-guard\.' "$HOOK_RULE_CFG" 2>/dev/null \
        | sed 's/^read-guard\.\([^.]*\)\..*/\1/' \
        | sort -u)
    return 0
}
