# Claude Setup

Utilities for setting up Claude Code in projects, including automated MCP server installation.

## Included Plugins & Skills

### MCP Server Installer Skill

Quickly add MCP servers from the team-insights template to any Claude Code project.

**How to use:**

1. Navigate to your project directory:
```bash
cd /path/to/your/project
```

2. Invoke Claude Code and mention adding MCP servers:
```bash
claude
```

3. In the conversation, say something like:
   - "Add MCP servers to this project"
   - "I want to install MCP servers from the template"
   - "Setup Serena, Ref, Exa, and Sequential Thinking"
   - "Configure MCP servers for this project"

4. The skill will:
   - Show you which MCP servers are available
   - Ask which ones you want to add
   - Create/update `.mcp.json` with your selections
   - Configure `.claude/settings.json` to enable project MCP servers
   - Provide feedback and next steps

**Available MCP Servers:**

- **Serena** - Code intelligence with LSP integration (symbol navigation, refactoring)
- **Ref** - Documentation and API reference search
- **Exa** - Advanced web search and code context retrieval
- **Sequential Thinking** - Enhanced reasoning for complex problems

**Next Steps After Installation:**

1. Restart Claude Code to load the new MCP servers
2. Verify servers are loaded by checking the tool list
3. Update API keys if needed (Ref and Exa use shared template keys)

## Installation

This plugin is in `/Users/agallentes/git/claude-setup`.

To use it in your projects:

1. Clone or reference the plugin:
```bash
# The plugin is located at:
/Users/agallentes/git/claude-setup
```

2. In Claude Code, reference it in your project (if using local plugins):
```bash
# Copy the plugin to your project's .claude/ directory
# Or configure Claude Code to load it globally
```

## Plugin Structure

```
claude-setup/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── skills/
│   └── mcp-installer/
│       └── SKILL.md         # MCP server installation skill
└── README.md                # This file
```

## Features

- **One-click MCP setup** - Add multiple servers with interactive selection
- **Smart merging** - Respects existing configurations, no data loss
- **Automatic backups** - Creates backups before modifying existing files
- **Clear feedback** - Shows exactly what was added and provides next steps
- **API keys included** - Template includes pre-configured keys (replace with your own)

## How the Skill Works

1. **Reads the template** - Loads MCP server definitions from `/Users/agallentes/git/team-insights/.mcp.json`
2. **Presents options** - Shows available servers and lets you choose
3. **Installs servers** - Updates your project's `.mcp.json` with selected servers
4. **Configures Claude Code** - Ensures `.claude/settings.json` has `enableAllProjectMcpServers: true`
5. **Provides guidance** - Shows next steps and how to verify the installation

## Troubleshooting

### Skill doesn't activate
Make sure you mention "add mcp", "setup mcp", "install mcp servers", or similar phrases.

### API keys are invalid
The template includes shared API keys that may be rate-limited. Replace them with your own:
- Open `.mcp.json` after installation
- Replace the Ref API key (`ref-...`) with your own
- Replace the Exa API key with your own

### Servers don't load after installation
1. Restart Claude Code completely (exit and run `claude` again)
2. Check that `.claude/settings.json` has `enableAllProjectMcpServers: true`
3. Verify `.mcp.json` has valid JSON syntax

### Can't write to files
Make sure you have write permissions in your project directory:
```bash
chmod 755 /path/to/project
chmod 644 /path/to/project/.mcp.json  # if it exists
```

## Support

For issues or questions about MCP servers, see:
- [MCP Documentation](https://modelcontextprotocol.io)
- [Claude Code Documentation](https://docs.claude.com)
- [Serena MCP Server](https://github.com/oraios/serena)
- [Exa MCP Server](https://github.com/exa-labs/exa-mcp-server)
