#!/usr/bin/env bash
# graphify-redirect.sh — PreToolUse advisory hook
# When graphify-out/graph.json exists in the current project, reminds agents
# to query the knowledge graph before doing raw file searches.
# This is advisory only: it never blocks tool calls.

PAYLOAD=$(cat -)
TOOL=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null)

# Only fire for structural search operations
[[ "$TOOL" == "Glob" || "$TOOL" == "Grep" ]] || exit 0

# Find project root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
GRAPH="$REPO_ROOT/graphify-out/graph.json"

[[ -f "$GRAPH" ]] || exit 0

# Soft nudge via stderr — model sees this as advisory context
>&2 cat <<'MSG'
[graphify] Knowledge graph available (graphify-out/graph.json).
For structural queries (architecture, relationships, dependencies):
  • graphify query "<question>"            — BFS traversal
  • graphify path "ConceptA" "ConceptB"   — shortest path
  • Read graphify-out/GRAPH_REPORT.md     — community overview
Using the graph is ~71x more token-efficient than raw file search.
MSG

exit 0
