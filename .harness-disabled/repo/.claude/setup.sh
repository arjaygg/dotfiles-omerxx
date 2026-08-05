#!/bin/bash
#
# Claude Code Configuration Setup Script
# This script sets up symlinks from ~/.claude to this dotfiles repository
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo -e "${BLUE}Setting up Claude Code configuration...${NC}"
echo -e "Dotfiles location: ${DOTFILES_DIR}"
echo -e "Target location: ${CLAUDE_DIR}\n"

# Create ~/.claude directory if it doesn't exist
if [ ! -d "$CLAUDE_DIR" ]; then
    echo -e "${YELLOW}Creating ${CLAUDE_DIR} directory${NC}"
    mkdir -p "$CLAUDE_DIR"
fi

# Function to create symlink safely
create_symlink() {
    local source="$1"
    local target="$2"
    local name="$3"

    if [ -L "$target" ]; then
        echo -e "${GREEN}✓${NC} ${name} already symlinked"
    elif [ -e "$target" ]; then
        echo -e "${YELLOW}⚠${NC}  ${name} exists, backing up to ${target}.backup"
        mv "$target" "${target}.backup"
        ln -s "$source" "$target"
        echo -e "${GREEN}✓${NC} ${name} symlinked"
    else
        ln -s "$source" "$target"
        echo -e "${GREEN}✓${NC} ${name} symlinked"
    fi
}

# Setup symlinks
echo -e "${BLUE}Creating symlinks...${NC}"
create_symlink "$DOTFILES_DIR/.claude/settings.json" "$CLAUDE_DIR/settings.json" "settings.json"
create_symlink "$DOTFILES_DIR/.claude/commands" "$CLAUDE_DIR/commands" "commands/"
create_symlink "$DOTFILES_DIR/.claude/output-styles" "$CLAUDE_DIR/output-styles" "output-styles/"
create_symlink "$DOTFILES_DIR/.claude/plugins" "$CLAUDE_DIR/plugins" "plugins/"
create_symlink "$DOTFILES_DIR/.claude/claude-statusline" "$CLAUDE_DIR/claude-statusline" "claude-statusline/"

echo -e "\n${BLUE}Initializing git submodules...${NC}"
cd "$DOTFILES_DIR"
if git submodule status | grep -q "^-"; then
    git submodule update --init --recursive
    echo -e "${GREEN}✓${NC} Submodules initialized"
else
    echo -e "${GREEN}✓${NC} Submodules already initialized"
fi

echo -e "\n${GREEN}Setup complete!${NC}"
echo -e "\n${BLUE}Next steps:${NC}"
echo -e "1. If you had existing plugins, restore marketplaces content:"
echo -e "   ${YELLOW}mv ~/.claude/plugins.backup/marketplaces ~/.claude/plugins/${NC}"
echo -e "2. Run Claude Code to verify configuration"
echo -e "3. Install any missing plugins from your installed_plugins.json"
