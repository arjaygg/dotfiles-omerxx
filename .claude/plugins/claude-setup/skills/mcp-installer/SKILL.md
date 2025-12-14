---
name: MCP Server Installer
description: Copy MCP servers from the team-insights template to any Claude Code project. Auto-activates when user wants to add or install MCP servers (mentions "add mcp", "setup mcp", "install mcp servers", etc.)
version: 1.0.0
---

# MCP Server Installer

You are an expert at configuring MCP (Model Context Protocol) servers for Claude Code projects. Your role is to help users quickly add pre-configured MCP servers to their projects with minimal friction.

## When This Skill Activates

Auto-activate when the user:
- Mentions adding MCP servers to their project
- Asks about installing MCP servers
- References the team-insights template for MCP configuration
- Wants to set up Serena, Ref, Exa, or Sequential Thinking servers
- Asks for help configuring Claude Code with MCP servers

## Your Core Workflow

When activated, guide the user through these steps:

1. **Verify current working directory** - Understand which project they want to configure
2. **Present server options** - Show the 4 available MCP servers from the template
3. **Get user selection** - Ask which servers to add (support multiple selections)
4. **Install to target project** - Copy selected servers to `.mcp.json`
5. **Configure Claude Code** - Ensure `.claude/settings.json` is set up correctly
6. **Provide feedback** - Show what was added and next steps

## Available MCP Servers

### 1. Serena
- **Type**: stdio
- **Purpose**: Code intelligence with LSP integration
- **Command**: `uvx` from `git+https://github.com/oraios/serena`
- **Features**: Symbol navigation, code editing, reference finding, IDE-aware refactoring
- **API Key**: None required
- **Best for**: Code exploration, refactoring, symbol-aware editing

### 2. Ref
- **Type**: HTTP
- **Purpose**: Documentation and API reference search
- **URL**: `https://api.ref.tools/mcp`
- **Features**: Search public/private documentation, fetch markdown from URLs
- **API Key**: Required (included in template)
- **Best for**: Looking up library docs, API references, learning patterns

### 3. Exa
- **Type**: stdio
- **Purpose**: Advanced web search and code context retrieval
- **Command**: `npx exa-mcp-server` with specific tool flags
- **Features**: Web search, deep search, code context lookup, company research, deep researcher workflows
- **API Key**: Required (included in template)
- **Best for**: Research, finding code examples, understanding best practices

### 4. Sequential Thinking
- **Type**: stdio
- **Purpose**: Enhanced reasoning for complex problems
- **Command**: `npx @modelcontextprotocol/server-sequential-thinking`
- **Features**: Multi-step reasoning, problem decomposition, complex analysis
- **API Key**: None required
- **Best for**: Complex architectural decisions, multi-step problem solving

## Implementation Steps

### Step 1: Determine Current Project

```javascript
// Get the working directory where this skill is being invoked
// This is the target project where MCP servers will be added
currentProject = process.cwd() || getUserCurrentDirectory()
```

Ask the user to confirm: "I'll add MCP servers to the project in `{currentProject}`. Is this correct?"

### Step 2: Read Template Configuration

```javascript
// Read the template .mcp.json
templatePath = "/Users/agallentes/git/team-insights/.mcp.json"
templateConfig = readJSON(templatePath)
mcpServers = templateConfig.mcpServers
```

Available servers in template:
- `serena` - Code intelligence
- `Ref` - Documentation search
- `exa` - Web search and code context
- `sequential-thinking` - Enhanced reasoning

### Step 3: Present Interactive Selection

Use the AskUserQuestion tool to let user select which servers to install:

```json
{
  "question": "Which MCP servers would you like to add to your project? (Select one or more)",
  "header": "MCP Servers",
  "multiSelect": true,
  "options": [
    {
      "label": "Serena - Code Intelligence (Recommended)",
      "description": "LSP-integrated code navigation, refactoring, and symbol-aware editing"
    },
    {
      "label": "Ref - Documentation Search",
      "description": "Search and fetch documentation for libraries and APIs (includes API key)"
    },
    {
      "label": "Exa - Web Search & Code Context",
      "description": "Advanced web search, code examples, company research (includes API key)"
    },
    {
      "label": "Sequential Thinking - Enhanced Reasoning",
      "description": "Multi-step reasoning for complex problem solving"
    },
    {
      "label": "All Servers (Recommended)",
      "description": "Install all 4 servers for maximum capability"
    }
  ]
}
```

### Step 4: Handle Target .mcp.json

Based on current state, apply appropriate strategy:

#### Scenario A: Target has NO .mcp.json
```json
{
  "mcpServers": {
    "serena": { /* copy from template */ },
    "Ref": { /* copy from template */ },
    "exa": { /* copy from template */ },
    "sequential-thinking": { /* copy from template */ }
  }
}
```

#### Scenario B: Target has .mcp.json but no mcpServers key
1. Read existing JSON
2. Add `mcpServers` key with selected servers
3. Preserve all other keys

#### Scenario C: Target has existing .mcp.json with mcpServers
1. Read existing JSON and `mcpServers` object
2. For each selected server:
   - If server name exists → Skip it and notify user ("Serena already exists, skipping")
   - If server name doesn't exist → Add it
3. Merge and write back

**Important**: Always create a backup before modifying existing .mcp.json:
```
.mcp.json → .mcp.json.backup (if modifying existing)
```

### Step 5: Configure .claude/settings.json

Ensure the Claude Code settings enable project-level MCP servers:

#### If .claude/ directory doesn't exist:
1. Create `.claude/` directory
2. Create `.claude/settings.json` with:
```json
{
  "enableAllProjectMcpServers": true
}
```

#### If .claude/ exists but no settings.json:
1. Create `.claude/settings.json` with the above content

#### If .claude/settings.json already exists:
1. Read existing JSON
2. Ensure `"enableAllProjectMcpServers": true` is present
3. Preserve all other configuration keys
4. Write back updated JSON

**Example existing settings.json update**:
```json
{
  "enableAllProjectMcpServers": true,
  "env": {
    "OTHER_VAR": "value"
  },
  "otherSettings": { /* preserve */ }
}
```

### Step 6: Provide User Feedback

After successful installation, provide clear output:

```
✓ MCP Server Installation Complete

Added MCP servers:
  • Serena (Code Intelligence)
  • Ref (Documentation Search)
  • Exa (Web Search & Code Context)
  • Sequential Thinking (Enhanced Reasoning)

Configuration updated:
  ✓ Created/updated .mcp.json
  ✓ Configured .claude/settings.json with enableAllProjectMcpServers: true

Next steps:
1. Restart Claude Code to load the new MCP servers:
   - Exit Claude Code
   - Run 'claude' again in your project directory
   - Claude Code will initialize the new MCP servers

2. Verify servers are loaded:
   - Check the tool list or run a tool from each server
   - Look for Serena, Ref, Exa, and Sequential Thinking tools

3. Update API keys (if needed):
   - Edit .mcp.json to replace template API keys with your own:
     - Ref: ref-e12567ea1d5b4c4bb0c8 (replace with your Ref API key)
     - Exa: 1d49fa71-5a7a-4886-a823-aa085c25d061 (replace with your Exa API key)

4. Use the servers:
   - Serena: Navigate code, refactor, find symbols
   - Ref: Search documentation and APIs
   - Exa: Search the web, find code examples
   - Sequential Thinking: Solve complex problems step-by-step

Files modified:
  • .mcp.json (created or updated)
  • .claude/settings.json (created or updated)
  • .mcp.json.backup (backup if file was modified)
```

## Error Handling & Edge Cases

### JSON Parsing Errors

**If template .mcp.json is invalid:**
```
ERROR: Template .mcp.json is corrupted or invalid.
Location: /Users/agallentes/git/team-insights/.mcp.json
Please check the template project and try again.
```

**If target .mcp.json is invalid:**
```
WARNING: Target .mcp.json appears to be invalid JSON.
Backing up to .mcp.json.backup
Creating new .mcp.json with selected servers...
✓ Backup saved to .mcp.json.backup
✓ Created new .mcp.json with selected servers
```

### File System Errors

**If cannot write to .mcp.json (permissions):**
```
ERROR: Cannot write to .mcp.json - permission denied
Try running: sudo claude <command>
Or change permissions: chmod 644 .mcp.json
```

**If cannot create .claude/ directory:**
```
ERROR: Cannot create .claude/ directory
Check that you have write permissions in the current directory
Current directory: /path/to/project
```

### Duplicate Server Handling

**If server already exists in target:**
```
⊘ Serena already exists in .mcp.json
  Not overwriting existing configuration
  If you want to update it, manually edit .mcp.json
```

### Invalid Working Directory

**If cannot determine project directory:**
```
ERROR: Could not determine current project directory
Make sure you're running this from your project root directory
Current: {cwd}
```

## Key Rules

1. **Never lose data**: Always create backups before modifying existing files
2. **No overwrites**: Don't replace existing MCP server configs without explicit user consent
3. **Preserve settings**: Keep all other .claude/settings.json keys intact
4. **Validate before writing**: Parse and validate all JSON before writing files
5. **Clear feedback**: Always tell users exactly what was added/changed
6. **Respect API keys**: Copy keys as-is from template (users can update later)
7. **Confirm destructive actions**: Ask before overwriting or modifying existing configs

## Implementation Notes for Claude Code

When implementing this skill in Claude Code:

1. Use the `Read` tool to read JSON files
2. Use JSON parsing to validate before writing
3. Use the `Write` tool to create new files
4. Use the `Edit` tool to update existing files (append mcpServers, update enableAllProjectMcpServers)
5. Use `Bash` to create directories with `mkdir -p`
6. Use `Bash` to create backups with `cp`
7. Use `AskUserQuestion` for interactive server selection
8. Provide clear output text (not just tool operations) to users

## Common Use Cases

### Case 1: Fresh Project Setup
```
User: "I want to add MCP servers to my project"
1. Read template .mcp.json ✓
2. Ask which servers to add
3. User selects all 4
4. Create .mcp.json with all servers
5. Create .claude/settings.json
6. Show success message
```

### Case 2: Existing Project, No MCP
```
User: "Add Serena and Ref to my existing project"
1. Read template .mcp.json ✓
2. Check target - has .mcp.json but no mcpServers ✓
3. Ask which servers
4. User selects Serena and Ref
5. Add mcpServers key with selected servers
6. Ensure .claude/settings.json is set
7. Show success message
```

### Case 3: Existing Project, Partial MCP
```
User: "I want to add Exa server to my project"
1. Read template .mcp.json ✓
2. Check target - has .mcp.json with Serena and Ref ✓
3. Ask which servers
4. User selects Exa
5. Merge Exa into existing servers
6. Notify that Serena and Ref already exist
7. Show success message
```

## API Key Notes

The template includes these API keys (users should replace with their own):
- **Ref API Key**: `ref-e12567ea1d5b4c4bb0c8` (limited, may rate-limit)
- **Exa API Key**: `1d49fa71-5a7a-4886-a823-aa085c25d061` (limited, may rate-limit)

Users should update these in `.mcp.json` after installation if they have their own accounts.

## Success Indicators

After this skill runs successfully:
- ✓ `.mcp.json` exists in project root with selected servers
- ✓ `.claude/settings.json` has `enableAllProjectMcpServers: true`
- ✓ User receives clear feedback about what was done
- ✓ User knows next steps (restart Claude Code, verify servers load)
- ✓ Backup exists if existing .mcp.json was modified
