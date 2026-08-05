# Primitive Reference — Full Details

Load this file only when you need specifics beyond what's in SKILL.md.

---

## Hook Lifecycle Events

| Event | When | Can Block | Common use |
|---|---|---|---|
| `SessionStart` | Session opens | No | Index codebase, load context |
| `InstructionsLoaded` | CLAUDE.md read | No | Validate config, warm caches |
| `UserPromptSubmit` | User sends message | No | Sync indexes, inject hints |
| `PreToolUse` | Before tool runs | **Yes** | Block dangerous commands, gate writes |
| `PostToolUse` | After tool completes | No | Log output, track stats |
| `Notification` | Notification sent | No | Alert routing |
| `PreCompact` | Before compaction | No | Save session state |
| `Stop` | Session ends | No | Write summary, run checks |
| `WorktreeCreate` | Worktree created | No | Copy configs, open tmux |
| `WorktreeRemove` | Worktree removed | No | Clean up tmux |

**Hook script template:**
```bash
#!/usr/bin/env bash
set -euo pipefail

TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')

# Guard: exit 0 on non-matching tools — NEVER skip this
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

COMMAND=$(echo "$TOOL_INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE "\bdangerous-pattern\b"; then
  echo "BLOCKED: reason why" >&2
  exit 2  # blocks the tool call
fi

exit 0  # allow
```

**Settings.json registration:**
```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [{ "type": "command", "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/my-hook.sh\"'" }]
  }
]
```

---

## Agent / SubAgent Types

| Type | Best for |
|---|---|
| `general-purpose` | Multi-step research, code search, complex tasks |
| `Explore` | Quick codebase exploration, file/keyword search |
| `Plan` | Implementation planning, architectural design |
| `claude-code-guide` | Claude Code API/SDK/feature questions |
| `mcp_config_manager` | JSON config manipulation across AI tools |

**Agent prompt template:**
```
You are a [role] agent handling [task].
Context: [what parent knows]
Task: [specific, bounded]
Output: [expected format]
Do NOT: [explicit constraints]
```

---

## Skill SKILL.md Anatomy

```yaml
---
name: kebab-case-name
description: >
  What it does + when to invoke it. Include trigger keywords.
  End with: "Use this skill whenever [trigger conditions] — invoke proactively."
version: 1.0.0
triggers:
  - trigger phrase one
  - trigger phrase two
---
```

Body sections:
1. **When to Use** — bullet conditions
2. **Instructions** — numbered steps with bash/tool snippets
3. **Examples** — `User: X → Action: Y`
4. **Related Skills** — cross-links

---

## MCP Server Registration

**Global (`~/.claude/settings.json`):**
```json
"mcpServers": {
  "my-server": {
    "command": "node",
    "args": ["/path/to/server.js"],
    "env": { "API_KEY": "${env:MY_API_KEY}" }
  }
}
```

**Project-local (`.mcp.json`):**
```json
{
  "mcpServers": {
    "project-tools": {
      "command": "npx",
      "args": ["-y", "@company/project-mcp-server"]
    }
  }
}
```

---

## Memory Format

Location: `~/.claude/projects/<project-slug>/memory/<name>.md`

```markdown
---
name: memory name
description: one-line description for relevance matching
type: user | feedback | project | reference
---

Memory content here.
```

Index at `MEMORY.md` — one line per entry, max 200 lines.

---

## Permissions Syntax

```json
"permissions": {
  "allow": ["mcp__*__*", "Bash(*)", "Read(*)"],
  "deny": [
    "Bash(rm -rf *)",
    "Bash(sudo *)",
    "Read(./.env)",
    "Edit(./secrets/**)"
  ],
  "defaultMode": "acceptEdits"
}
```

Pattern: `ToolName(glob)` — e.g. `Bash(git push --force*)`, `Read(~/.ssh/*)`

`defaultMode` options: `acceptEdits` | `default` | `bypassPermissions`
