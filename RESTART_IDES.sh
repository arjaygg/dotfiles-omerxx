#!/bin/bash

# IDE Restart & Verification Script
# Usage: bash RESTART_IDES.sh

set -e

echo "🔄 IDE Restart & Verification"
echo "======================================"
echo ""

# Kill running instances
echo "1️⃣  Killing running IDE instances..."
killall Cursor 2>/dev/null || echo "   Cursor not running"
killall Windsurf 2>/dev/null || echo "   Windsurf not running"
sleep 1

# Verify symlinks
echo ""
echo "2️⃣  Verifying configuration symlinks..."
CURSOR_SETTINGS=~/Library/Application\ Support/Cursor/User/settings.json
CURSOR_KEYBINDINGS=~/Library/Application\ Support/Cursor/User/keybindings.json
WINDSURF_SETTINGS=~/Library/Application\ Support/Windsurf/User/settings.json
WINDSURF_KEYBINDINGS=~/Library/Application\ Support/Windsurf/User/keybindings.json

check_symlink() {
  if [ -f "$1" ]; then
    echo "   ✅ $2"
  else
    echo "   ❌ $2 (MISSING)"
  fi
}

check_symlink "$CURSOR_SETTINGS" "Cursor settings.json"
check_symlink "$CURSOR_KEYBINDINGS" "Cursor keybindings.json"
check_symlink "$WINDSURF_SETTINGS" "Windsurf settings.json"
check_symlink "$WINDSURF_KEYBINDINGS" "Windsurf keybindings.json"

# Verify JSON validity
echo ""
echo "3️⃣  Validating JSON configuration..."
python3 -c "import json; json.load(open('$CURSOR_SETTINGS'))" 2>/dev/null && echo "   ✅ Cursor settings valid" || echo "   ❌ Cursor settings invalid"
python3 -c "import json; json.load(open('$CURSOR_KEYBINDINGS'))" 2>/dev/null && echo "   ✅ Cursor keybindings valid" || echo "   ❌ Cursor keybindings invalid"
python3 -c "import json; json.load(open('$WINDSURF_SETTINGS'))" 2>/dev/null && echo "   ✅ Windsurf settings valid" || echo "   ❌ Windsurf settings invalid"
python3 -c "import json; json.load(open('$WINDSURF_KEYBINDINGS'))" 2>/dev/null && echo "   ✅ Windsurf keybindings valid" || echo "   ❌ Windsurf keybindings invalid"

# Launch IDEs
echo ""
echo "4️⃣  Launching IDEs..."
open -a Cursor &
open -a Windsurf &

echo ""
echo "✅ Done! Both IDEs launching..."
echo ""
echo "📋 Verification Checklist (After IDEs load):"
echo ""
echo "   Cursor:"
echo "   - [ ] Font size looks comfortable (should be 17px)"
echo "   - [ ] Theme is 'Catppuccin Mocha'"
echo "   - [ ] Minimap is hidden (left sidebar cleaner)"
echo "   - [ ] Try cmd+i to open Agent mode"
echo "   - [ ] Try cmd+/ to toggle comment"
echo ""
echo "   Windsurf:"
echo "   - [ ] Font size looks comfortable (should be 17px)"
echo "   - [ ] Theme is 'Catppuccin Mocha'"
echo "   - [ ] Minimap is hidden (left sidebar cleaner)"
echo "   - [ ] Try cmd+k to open Prioritized Commands"
echo "   - [ ] Try cmd+/ to toggle comment"
echo ""
echo "📚 Guides:"
echo "   - Cursor: .cursor/CURSOR_SETUP_GUIDE.md"
echo "   - Windsurf: windsurf/WINDSURF_SETUP_GUIDE.md"
echo "   - Summary: IDE_OPTIMIZATION_SUMMARY.md"
echo ""
