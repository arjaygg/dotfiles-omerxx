#!/usr/bin/env bash
# PreToolUse: non-blocking advisory on Write when creating NOTES/TODO/SCRATCH/TEMP outside designated dirs
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.file_path // ""' 2>/dev/null || echo "")

# Allow writes to safe directories
[[ "$FILE_PATH" == */docs/* || "$FILE_PATH" == */plans/* || "$FILE_PATH" == */.claude/* || "$FILE_PATH" == */ai/* ]] && exit 0

# Check filename pattern for temporary file indicators
BASENAME=$(basename "$FILE_PATH" 2>/dev/null || echo "")
if [[ "$BASENAME" =~ ^(NOTES|TODO|SCRATCH|TEMP) ]]; then
    echo "[DOC_FILE_ADVISORY] Creating $BASENAME outside docs/, plans/, .claude/, or ai/ directory." >&2
    echo "  Consider moving temporary notes to plans/ instead." >&2
fi

exit 0
