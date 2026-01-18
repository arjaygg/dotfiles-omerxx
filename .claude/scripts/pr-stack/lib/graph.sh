#!/usr/bin/env bash

# graph.sh - Visual dependency graph generation
# Generates ASCII, Mermaid, and DOT format graphs for PR stacks

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/validation.sh"
source "$SCRIPT_DIR/worktree-charcoal.sh"

# ============================================================================
# Data Collection
# ============================================================================

# Build branch hierarchy from stack info
# Populates: BRANCH_PARENTS, BRANCH_CHILDREN, ROOT_BRANCHES
build_branch_hierarchy() {
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    # Reset arrays
    declare -gA BRANCH_PARENTS
    declare -gA BRANCH_CHILDREN
    declare -ga ROOT_BRANCHES

    if [ ! -f "$stack_info_file" ]; then
        return 1
    fi

    # Read stack info
    while IFS=: read -r branch parent timestamp; do
        if [ -n "$branch" ] && [ -n "$parent" ]; then
            BRANCH_PARENTS["$branch"]="$parent"
            BRANCH_CHILDREN["$parent"]+="$branch "
        fi
    done < "$stack_info_file"

    # Find root branches (those whose parent is not in the stack)
    for branch in "${!BRANCH_PARENTS[@]}"; do
        local parent="${BRANCH_PARENTS[$branch]}"
        if [ -z "${BRANCH_PARENTS[$parent]}" ]; then
            # Parent is not tracked, this is a root
            ROOT_BRANCHES+=("$branch")
        fi
    done
}

# Get PR info for a branch
# Args: $1 - branch name
# Returns: "PR_ID:STATUS" or empty
get_branch_pr_info() {
    local branch=$1
    local pr_created_file
    pr_created_file="$(git rev-parse --git-path pr-created 2>/dev/null)"

    if [ ! -f "$pr_created_file" ]; then
        echo ""
        return
    fi

    while IFS=: read -r b target pr_id timestamp; do
        if [ "$b" == "$branch" ]; then
            echo "$pr_id"
            return
        fi
    done < "$pr_created_file"

    echo ""
}

# ============================================================================
# ASCII Graph Generation
# ============================================================================

# Generate ASCII graph
# Args: $1 - show PR info (true/false)
generate_ascii_graph() {
    local show_pr_info=${1:-true}

    build_branch_hierarchy

    if [ ${#ROOT_BRANCHES[@]} -eq 0 ]; then
        echo "No branches in stack"
        return 1
    fi

    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                   STACK DEPENDENCY GRAPH                   ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Find the trunk (common parent of all roots)
    local trunk="main"
    for branch in "${ROOT_BRANCHES[@]}"; do
        if [ -n "${BRANCH_PARENTS[$branch]}" ]; then
            trunk="${BRANCH_PARENTS[$branch]}"
            break
        fi
    done

    # Print trunk
    echo -e "${CYAN}${trunk}${NC}"

    # Sort roots by name for consistent output
    IFS=$'\n' sorted_roots=($(sort <<<"${ROOT_BRANCHES[*]}"))
    unset IFS

    local root_count=${#sorted_roots[@]}
    local root_idx=0

    for root in "${sorted_roots[@]}"; do
        root_idx=$((root_idx + 1))
        local is_last=$([[ $root_idx -eq $root_count ]] && echo true || echo false)
        print_ascii_branch "$root" "" "$is_last" "$show_pr_info"
    done

    echo ""
}

# Print a branch and its children recursively
# Args: $1 - branch, $2 - prefix, $3 - is_last, $4 - show_pr_info
print_ascii_branch() {
    local branch=$1
    local prefix=$2
    local is_last=$3
    local show_pr_info=$4

    # Connector
    if [ "$is_last" == "true" ]; then
        echo -n -e "${prefix}└── "
        local child_prefix="${prefix}    "
    else
        echo -n -e "${prefix}├── "
        local child_prefix="${prefix}│   "
    fi

    # Branch name (highlight current)
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null)
    if [ "$branch" == "$current_branch" ]; then
        echo -n -e "${GREEN}${branch}${NC}"
    else
        echo -n -e "${CYAN}${branch}${NC}"
    fi

    # Worktree info
    local wt_path
    wt_path=$(get_worktree_path "$branch" 2>/dev/null)
    if [ -n "$wt_path" ]; then
        echo -n -e " ${YELLOW}[WT: $wt_path]${NC}"
    fi

    # PR info
    if [ "$show_pr_info" == "true" ]; then
        local pr_id
        pr_id=$(get_branch_pr_info "$branch")
        if [ -n "$pr_id" ]; then
            echo -n -e " ${BLUE}(PR #$pr_id)${NC}"
        fi
    fi

    echo "" # newline

    # Print children
    local children="${BRANCH_CHILDREN[$branch]}"
    if [ -n "$children" ]; then
        local child_array=($children)
        local child_count=${#child_array[@]}
        local child_idx=0

        # Sort children
        IFS=$'\n' sorted_children=($(sort <<<"${child_array[*]}"))
        unset IFS

        for child in "${sorted_children[@]}"; do
            child_idx=$((child_idx + 1))
            local child_is_last=$([[ $child_idx -eq $child_count ]] && echo true || echo false)
            print_ascii_branch "$child" "$child_prefix" "$child_is_last" "$show_pr_info"
        done
    fi
}

# ============================================================================
# Mermaid Graph Generation
# ============================================================================

# Generate Mermaid diagram
generate_mermaid_graph() {
    build_branch_hierarchy

    if [ ${#ROOT_BRANCHES[@]} -eq 0 ]; then
        echo "No branches in stack"
        return 1
    fi

    echo '```mermaid'
    echo 'graph TD'

    # Find trunk
    local trunk="main"
    for branch in "${ROOT_BRANCHES[@]}"; do
        if [ -n "${BRANCH_PARENTS[$branch]}" ]; then
            trunk="${BRANCH_PARENTS[$branch]}"
            break
        fi
    done

    # Sanitize branch names for Mermaid (replace / with _)
    sanitize_mermaid_id() {
        echo "$1" | tr '/' '_' | tr '-' '_'
    }

    # Add trunk node
    local trunk_id
    trunk_id=$(sanitize_mermaid_id "$trunk")
    echo "    ${trunk_id}[${trunk}]"

    # Track edges to avoid duplicates
    declare -A edges_printed

    # Print all branches and edges
    for branch in "${!BRANCH_PARENTS[@]}"; do
        local parent="${BRANCH_PARENTS[$branch]}"
        local branch_id
        branch_id=$(sanitize_mermaid_id "$branch")
        local parent_id
        parent_id=$(sanitize_mermaid_id "$parent")

        # Add node with display name
        local pr_id
        pr_id=$(get_branch_pr_info "$branch")
        if [ -n "$pr_id" ]; then
            echo "    ${branch_id}[\"${branch}<br/>PR #${pr_id}\"]"
        else
            echo "    ${branch_id}[${branch}]"
        fi

        # Add edge
        local edge_key="${parent_id}_${branch_id}"
        if [ -z "${edges_printed[$edge_key]}" ]; then
            echo "    ${parent_id} --> ${branch_id}"
            edges_printed["$edge_key"]=1
        fi
    done

    # Style current branch
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null)
    if [ -n "$current_branch" ]; then
        local current_id
        current_id=$(sanitize_mermaid_id "$current_branch")
        echo ""
        echo "    style ${current_id} fill:#90EE90,stroke:#228B22"
    fi

    echo '```'
}

# ============================================================================
# DOT (Graphviz) Graph Generation
# ============================================================================

# Generate DOT format graph
generate_dot_graph() {
    build_branch_hierarchy

    if [ ${#ROOT_BRANCHES[@]} -eq 0 ]; then
        echo "No branches in stack"
        return 1
    fi

    echo 'digraph PRStack {'
    echo '    rankdir=TB;'
    echo '    node [shape=box, style=rounded];'
    echo ''

    # Find trunk
    local trunk="main"
    for branch in "${ROOT_BRANCHES[@]}"; do
        if [ -n "${BRANCH_PARENTS[$branch]}" ]; then
            trunk="${BRANCH_PARENTS[$branch]}"
            break
        fi
    done

    # Sanitize names for DOT
    sanitize_dot_id() {
        echo "\"$1\""
    }

    # Add trunk node
    echo "    $(sanitize_dot_id "$trunk") [label=\"$trunk\", style=\"rounded,filled\", fillcolor=\"lightblue\"];"

    # Get current branch for highlighting
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null)

    # Print all branches
    for branch in "${!BRANCH_PARENTS[@]}"; do
        local parent="${BRANCH_PARENTS[$branch]}"
        local pr_id
        pr_id=$(get_branch_pr_info "$branch")

        # Node label
        local label="$branch"
        if [ -n "$pr_id" ]; then
            label="$branch\\nPR #$pr_id"
        fi

        # Node style
        local style="rounded"
        local fillcolor="white"
        if [ "$branch" == "$current_branch" ]; then
            style="rounded,filled"
            fillcolor="lightgreen"
        fi

        echo "    $(sanitize_dot_id "$branch") [label=\"$label\", style=\"$style\", fillcolor=\"$fillcolor\"];"

        # Edge
        echo "    $(sanitize_dot_id "$parent") -> $(sanitize_dot_id "$branch");"
    done

    echo '}'
}

# ============================================================================
# Main Graph Function
# ============================================================================

# Generate graph in specified format
# Args: $1 - format (ascii, mermaid, dot)
graph_main() {
    local format=${1:-ascii}

    case "$format" in
        ascii|tree)
            generate_ascii_graph true
            ;;
        mermaid|md)
            generate_mermaid_graph
            ;;
        dot|graphviz)
            generate_dot_graph
            ;;
        *)
            echo "Unknown format: $format"
            echo "Supported formats: ascii, mermaid, dot"
            return 1
            ;;
    esac
}

# Export functions
export -f build_branch_hierarchy 2>/dev/null || true
export -f get_branch_pr_info 2>/dev/null || true
export -f generate_ascii_graph 2>/dev/null || true
export -f print_ascii_branch 2>/dev/null || true
export -f generate_mermaid_graph 2>/dev/null || true
export -f generate_dot_graph 2>/dev/null || true
export -f graph_main 2>/dev/null || true
