#!/usr/bin/env bash
# lit-ingest.sh — Parse a binary doc with LiteParse and ingest into the claude-pdf-context QMD collection.
#
# Usage:
#   lit-ingest.sh <file-path> [slug]
#
# Arguments:
#   file-path   Path to a PDF, DOCX, XLSX, PPTX, or image file
#   slug        Optional output filename (without .md). Defaults to lowercased basename.
#
# After ingestion, the doc is immediately searchable via:
#   mcp__qmd__search({ collection: "claude-pdf-context", query: "..." })

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: lit-ingest.sh <file-path> [slug]" >&2
  exit 1
fi

FILE="$1"

if [ ! -f "$FILE" ]; then
  echo "Error: file not found: $FILE" >&2
  exit 1
fi

if ! command -v lit &>/dev/null; then
  echo "Error: 'lit' CLI not found. Install with: npm i -g @llamaindex/liteparse" >&2
  exit 1
fi

SLUG="${2:-$(basename "$FILE" | sed 's/\.[^.]*$//' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cs 'a-z0-9-' '-' | sed 's/--*/-/g; s/^-//; s/-$//')}"
OUT_DIR="$HOME/.local/share/claude-pdf-index"
OUT_FILE="$OUT_DIR/${SLUG}.md"

mkdir -p "$OUT_DIR"

echo "Parsing: $FILE"
lit parse "$FILE" --format markdown -o "$OUT_FILE"

echo "Ingested: $OUT_FILE"
echo "Collection: claude-pdf-context"
echo "Query with: mcp__qmd__search({ collection: \"claude-pdf-context\", query: \"...\" })"
