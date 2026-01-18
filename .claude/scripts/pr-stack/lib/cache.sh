#!/usr/bin/env bash

# cache.sh - Caching layer for Azure DevOps API calls
# Provides 5-minute TTL caching to reduce API calls and improve performance

# Get cache directory (inside .git for repo-specific caching)
get_cache_dir() {
    local git_dir
    git_dir=$(git rev-parse --git-common-dir 2>/dev/null || git rev-parse --git-dir)
    echo "$git_dir/pr-stack-cache"
}

# Initialize cache directory
init_cache() {
    local cache_dir
    cache_dir=$(get_cache_dir)
    mkdir -p "$cache_dir"
}

# Get cache file path for a key
# Args: $1 - cache key (e.g., "pr-status-12345")
get_cache_file() {
    local key=$1
    local cache_dir
    cache_dir=$(get_cache_dir)
    echo "$cache_dir/${key}.cache"
}

# Check if cache entry is valid (exists and not expired)
# Args: $1 - cache key, $2 - TTL in seconds (default: 300 = 5 minutes)
# Returns: 0 if valid, 1 if expired/missing
is_cache_valid() {
    local key=$1
    local ttl=${2:-300}
    local cache_file
    cache_file=$(get_cache_file "$key")

    if [ ! -f "$cache_file" ]; then
        return 1
    fi

    local file_age
    local current_time
    current_time=$(date +%s)

    # Get file modification time (portable across macOS and Linux)
    if stat --version &>/dev/null 2>&1; then
        # GNU stat (Linux)
        file_age=$(stat -c %Y "$cache_file")
    else
        # BSD stat (macOS)
        file_age=$(stat -f %m "$cache_file")
    fi

    local age=$((current_time - file_age))

    if [ "$age" -lt "$ttl" ]; then
        return 0
    fi

    return 1
}

# Get cached value
# Args: $1 - cache key
# Returns: cached value via stdout, or empty if not found
cache_get() {
    local key=$1
    local cache_file
    cache_file=$(get_cache_file "$key")

    if [ -f "$cache_file" ]; then
        cat "$cache_file"
    fi
}

# Set cache value
# Args: $1 - cache key, $2 - value
cache_set() {
    local key=$1
    local value=$2
    local cache_file
    cache_file=$(get_cache_file "$key")

    init_cache
    echo "$value" > "$cache_file"
}

# Clear cache for a key
# Args: $1 - cache key
cache_clear() {
    local key=$1
    local cache_file
    cache_file=$(get_cache_file "$key")

    rm -f "$cache_file"
}

# Clear all cache
cache_clear_all() {
    local cache_dir
    cache_dir=$(get_cache_dir)
    rm -rf "$cache_dir"
}

# Get PR status with caching
# Args: $1 - PR ID
# Returns: PR status (active, completed, abandoned, unknown)
cached_get_pr_status() {
    local pr_id=$1
    local cache_key="pr-status-$pr_id"

    # Check cache first
    if is_cache_valid "$cache_key" 300; then
        cache_get "$cache_key"
        return 0
    fi

    # Cache miss - fetch from API
    local status
    status=$(az repos pr show --id "$pr_id" \
        --organization "https://dev.azure.com/bofaz" \
        --query "status" -o tsv 2>/dev/null || echo "unknown")

    # Cache the result
    cache_set "$cache_key" "$status"

    echo "$status"
}

# Fetch all PR statuses in parallel
# Args: $@ - List of PR IDs
# Returns: JSON-like output "pr_id:status" for each PR
fetch_pr_statuses_parallel() {
    local pr_ids=("$@")
    local cache_dir
    cache_dir=$(get_cache_dir)
    init_cache

    local pids=()
    local temp_dir
    temp_dir=$(mktemp -d)

    for pr_id in "${pr_ids[@]}"; do
        if [ -z "$pr_id" ]; then
            continue
        fi

        local cache_key="pr-status-$pr_id"

        # Check cache first
        if is_cache_valid "$cache_key" 300; then
            local cached_status
            cached_status=$(cache_get "$cache_key")
            echo "$pr_id:$cached_status" > "$temp_dir/$pr_id"
        else
            # Fetch in background
            (
                local status
                status=$(az repos pr show --id "$pr_id" \
                    --organization "https://dev.azure.com/bofaz" \
                    --query "status" -o tsv 2>/dev/null || echo "unknown")

                cache_set "$cache_key" "$status"
                echo "$pr_id:$status" > "$temp_dir/$pr_id"
            ) &
            pids+=($!)
        fi
    done

    # Wait for all background jobs
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    # Collect results
    for pr_id in "${pr_ids[@]}"; do
        if [ -f "$temp_dir/$pr_id" ]; then
            cat "$temp_dir/$pr_id"
        fi
    done

    # Cleanup
    rm -rf "$temp_dir"
}

# Build a map of PR statuses (call once, use many times)
# Args: $1 - associative array name to populate, $@ - PR IDs
# Usage: declare -A PR_STATUSES; build_pr_status_map PR_STATUSES 123 456 789
build_pr_status_map() {
    local -n status_map=$1
    shift
    local pr_ids=("$@")

    # Fetch all in parallel
    local results
    results=$(fetch_pr_statuses_parallel "${pr_ids[@]}")

    # Parse results into map
    while IFS=: read -r pr_id status; do
        if [ -n "$pr_id" ] && [ -n "$status" ]; then
            status_map["$pr_id"]="$status"
        fi
    done <<< "$results"
}

# Get CI/CD build status with caching
# Args: $1 - branch name
# Returns: Build status (succeeded, failed, inProgress, notStarted, unknown)
cached_get_build_status() {
    local branch=$1
    local cache_key="build-status-$(echo "$branch" | tr '/' '-')"

    # Check cache first (shorter TTL for builds - 60 seconds)
    if is_cache_valid "$cache_key" 60; then
        cache_get "$cache_key"
        return 0
    fi

    # Try to get latest build for this branch
    local status
    status=$(az pipelines build list \
        --organization "https://dev.azure.com/bofaz" \
        --branch "$branch" \
        --top 1 \
        --query "[0].result" -o tsv 2>/dev/null || echo "unknown")

    # Cache the result
    cache_set "$cache_key" "$status"

    echo "$status"
}

# Export functions
export -f get_cache_dir 2>/dev/null || true
export -f init_cache 2>/dev/null || true
export -f get_cache_file 2>/dev/null || true
export -f is_cache_valid 2>/dev/null || true
export -f cache_get 2>/dev/null || true
export -f cache_set 2>/dev/null || true
export -f cache_clear 2>/dev/null || true
export -f cache_clear_all 2>/dev/null || true
export -f cached_get_pr_status 2>/dev/null || true
export -f fetch_pr_statuses_parallel 2>/dev/null || true
export -f build_pr_status_map 2>/dev/null || true
export -f cached_get_build_status 2>/dev/null || true
