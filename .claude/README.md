# Claude Code Configuration

This directory contains configuration files for [Claude Code](https://claude.com/claude-code), Anthropic's official CLI tool.

## Structure

```
.claude/
├── README.md                 # This file
├── setup.sh                  # Setup script for new machines
├── .gitignore               # Excludes runtime/cache files
├── settings.json            # Main Claude Code settings
├── commands/                # Custom slash commands
│   └── smart-commit.md
├── output-styles/           # Custom output style prompts
│   ├── strategic-analyst.md
│   └── technical-lead.md
├── plugins/                 # Plugin configuration
│   ├── installed_plugins.json
│   ├── known_marketplaces.json
│   └── marketplaces/        # Downloaded plugins (not tracked)
└── claude-statusline/       # Git submodule for statusline
    └── statusline.sh
```

## Components

### settings.json
Main configuration file containing:
- Model selection (`sonnet[1m]`)
- Status line configuration
- Enabled plugins
- Feature flags (e.g., `alwaysThinkingEnabled`)

### commands/
Custom slash commands that extend Claude Code functionality. Commands are markdown files with frontmatter.

**Usage:** `/command-name` in Claude Code

**Example:** `/smart-commit` - Intelligent git commit helper

### output-styles/
Custom system prompt replacements that change Claude's behavior and output format.

**Usage:** `/output-style style-name` in Claude Code

**Available styles:**
- `strategic-analyst` - For document analysis and business intelligence
- `technical-lead` - Technical leadership and architecture guidance

### plugins/
Plugin management configuration:
- `installed_plugins.json` - Tracks which plugins are installed
- `known_marketplaces.json` - Plugin marketplace sources
- `marketplaces/` - Downloaded plugin content (excluded from git, like `node_modules`)

### claude-statusline/
Git submodule from [dwillitzer/claude-statusline](https://github.com/dwillitzer/claude-statusline) that provides a custom status line display.

## Setup Instructions

### First-Time Setup (New Machine)

1. **Clone your dotfiles repository:**
   ```bash
   git clone <your-dotfiles-repo> ~/.dotfiles
   cd ~/.dotfiles
   ```

2. **Run the setup script:**
   ```bash
   ./.claude/setup.sh
   ```

3. **Install plugins (if needed):**
   - The setup preserves plugin configuration
   - Re-install plugins through Claude Code marketplace if needed
   - Or restore from backup: `mv ~/.claude/plugins.backup/marketplaces ~/.claude/plugins/`

### Manual Setup

If you prefer to set up manually:

```bash
# Create ~/.claude directory
mkdir -p ~/.claude

# Initialize submodules
cd ~/.dotfiles
git submodule update --init --recursive

# Create symlinks
ln -s ~/.dotfiles/.claude/settings.json ~/.claude/settings.json
ln -s ~/.dotfiles/.claude/commands ~/.claude/commands
ln -s ~/.dotfiles/.claude/output-styles ~/.claude/output-styles
ln -s ~/.dotfiles/.claude/plugins ~/.claude/plugins
ln -s ~/.dotfiles/.claude/claude-statusline ~/.claude/claude-statusline
```

## What's Excluded from Git

The following directories are excluded via `.gitignore` as they contain runtime/cache data:

- `debug/` - Debug logs
- `downloads/` - Downloaded files
- `file-history/` - File modification history
- `history.jsonl` - Conversation history
- `ide/` - IDE integration data
- `projects/` - Project-specific data
- `session-env/` - Session environment data
- `shell-snapshots/` - Shell state snapshots
- `statsig/` - Analytics data
- `todos/` - Todo list data
- `plugins/marketplaces/` - Downloaded plugins (restored on setup)

## Customization

### Adding a New Command

1. Create a markdown file in `commands/`:
   ```bash
   touch ~/.dotfiles/.claude/commands/my-command.md
   ```

2. Add frontmatter and content:
   ```markdown
   ---
   name: my-command
   description: Description of what this command does
   ---

   Your command prompt here...
   ```

3. Use with `/my-command` in Claude Code

### Adding a New Output Style

1. Create a markdown file in `output-styles/`:
   ```bash
   touch ~/.dotfiles/.claude/output-styles/my-style.md
   ```

2. Add frontmatter and system prompt:
   ```markdown
   ---
   name: my-style
   description: Description of this output style
   ---

   Your custom system prompt here...
   ```

3. Activate with `/output-style my-style` in Claude Code

### Modifying Settings

Edit `settings.json` directly:
```bash
vim ~/.dotfiles/.claude/settings.json
```

Changes take effect immediately (Claude Code watches the file).

## Updating

### Update Submodules (claude-statusline)

```bash
cd ~/.dotfiles
git submodule update --remote --merge
git add .claude/claude-statusline
git commit -m "Update claude-statusline submodule"
```

### Update Plugins

Plugins are managed through Claude Code's marketplace. The `installed_plugins.json` tracks which plugins you have installed, but the actual plugin code lives in `marketplaces/` (excluded from git).

To sync plugins to a new machine:
1. The setup script preserves `installed_plugins.json`
2. Claude Code will re-download plugins as needed
3. Or manually reinstall via the marketplace UI

## Troubleshooting

### Symlinks Not Working

Verify symlinks exist:
```bash
ls -la ~/.claude/ | grep -E "(commands|output-styles|settings.json|plugins|claude-statusline)"
```

All should show `->` pointing to your dotfiles directory.

### Submodule Not Initialized

```bash
cd ~/.dotfiles
git submodule status
# If showing `-` prefix, run:
git submodule update --init --recursive
```

### Plugin Issues

If plugins aren't loading:
1. Check `~/.claude/plugins/installed_plugins.json` exists
2. Verify `~/.claude/plugins/marketplaces/` has content
3. Reinstall plugins through Claude Code marketplace

### Statusline Not Working

1. Verify the submodule is initialized
2. Check the script is executable: `chmod +x ~/.claude/claude-statusline/statusline.sh`
3. Test manually: `bash ~/.claude/claude-statusline/statusline.sh`

## References

- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [Claude Statusline Repository](https://github.com/dwillitzer/claude-statusline)
- [Creating Custom Commands](https://docs.claude.com/en/docs/claude-code/custom-commands)
- [Creating Output Styles](https://docs.claude.com/en/docs/claude-code/output-styles)
