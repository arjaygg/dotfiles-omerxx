#!/usr/bin/env bash
# Install TDD Guard Lite into a project.
# Usage: bash ~/.dotfiles/ai/hooks/tdd-guard-lite/install.sh [project_dir]
#
# What this does:
#   1. Checks Python 3 is available
#   2. Optionally installs tree-sitter-languages (AST diff support)
#   3. Creates .claude/tdd-guard-lite.json (if missing)
#   4. Registers the PreToolUse hook in .claude/settings.json

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(pwd)}"

echo "==> TDD Guard Lite — installing into $PROJECT_DIR"

# 1. Python 3 required
python3 --version >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }

# 2. tree-sitter-languages (optional; enables AST diff for TS/JS/Python/Go)
if ! python3 -c "import tree_sitter_languages" 2>/dev/null; then
    read -r -p "Install tree-sitter-languages for AST diff? [Y/n] " yn
    case "${yn:-Y}" in
        [Yy]*)
            echo "Installing tree-sitter-languages..."
            pip install --quiet tree-sitter tree-sitter-languages
            ;;
        *)
            echo "Skipping — AST diff will be disabled; state machine only."
            ;;
    esac
fi

# 3. Per-project config
mkdir -p "$PROJECT_DIR/.claude/tdd-guard/data"
CONFIG="$PROJECT_DIR/.claude/tdd-guard-lite.json"
if [ ! -f "$CONFIG" ]; then
    cat > "$CONFIG" <<'JSON'
{
  "language": "auto",
  "testResultsPath": ".claude/tdd-guard/data/test.json",
  "modificationsPath": ".claude/tdd-guard/data/modifications.json",
  "sourcePatterns": [
    "src/**/*.ts", "src/**/*.tsx",
    "src/**/*.js", "src/**/*.jsx",
    "src/**/*.py",
    "**/*.go"
  ],
  "testPatterns": [
    "**/*.test.ts", "**/*.spec.ts",
    "**/*.test.js", "**/*.spec.js",
    "**/*_test.py", "**/test_*.py",
    "**/*_test.go"
  ],
  "astDiffEnabled": true,
  "recentModificationWindow": 10
}
JSON
    echo "    Created $CONFIG — edit patterns to match your project."
else
    echo "    $CONFIG already exists — skipping."
fi

# 4. Register hook in .claude/settings.json
SETTINGS="$PROJECT_DIR/.claude/settings.json"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

python3 - "$SETTINGS" "$HOOK_DIR/hook.sh" << 'PYTHON'
import json, sys

settings_path, hook_path = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])

for entry in pre:
    if isinstance(entry, dict):
        for h in entry.get("hooks", []):
            if hook_path in str(h.get("command", "")):
                print(f"    Hook already registered in {settings_path}")
                sys.exit(0)

pre.append({
    "matcher": "Write|Edit|MultiEdit",
    "hooks": [{"type": "command", "command": hook_path}]
})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print(f"    Registered hook in {settings_path}")
PYTHON

chmod +x "$HOOK_DIR/hook.sh"

echo ""
echo "==> Done. Next steps:"
echo "    1. Set up a test reporter to write test results:"
echo "       npm install -D tdd-guard-vitest   (vitest)"
echo "       npm install -D tdd-guard-jest      (jest)"
echo "       pip install tdd-guard-pytest       (pytest)"
echo "    2. Edit $CONFIG for your file patterns"
echo "    3. Run your tests once to generate the initial test.json"
