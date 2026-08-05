---
name: claude-architect
description: >
  Expert architect for Claude Code primitives — Skills, Agents, SubAgents, Hooks, Commands,
  MCP Servers, Memory, Plans, Worktrees, and Permissions. Decides which primitive to build,
  designs it from the correct pattern, and creates or edits the artifact.
  Understands every SDLC role (Dev, QA, TL, Architect, DevOps, PM) and maps each to the
  right Claude capability. Invoke when: "create a skill", "add a hook", "design a subagent",
  "build a command", "set up an MCP server", "automate when X happens", "which primitive should I use".
version: 1.0.0
triggers:
  - create a skill
  - create skill
  - new skill
  - add a hook
  - create a hook
  - design a subagent
  - create subagent
  - create agent
  - build a command
  - new command
  - create slash command
  - set up mcp
  - add mcp server
  - automate when
  - which primitive
  - what primitive
  - should i use a skill or
  - should i use a hook or
  - should i use an agent or
  - claude architect
  - design a claude primitive
  - configure permissions
  - add permission
  - todowrite vs task
  - when to use todowrite
---

# Claude Architect

**Creates and designs Claude Code primitives.** Combines expert knowledge of Claude's native
capabilities with SDLC role awareness to choose the right primitive for every automation need.

---

## Primitive Decision Tree

The first job of this skill is always to **select the right primitive**. Use this tree before designing anything.

```
What are you automating?
│
├── Triggered by user running a slash command (e.g. /review, /commit)?
│   └── → SKILL (user-invocable, conversational, can use all tools)
│
├── Triggered automatically when something happens (tool runs, session starts)?
│   └── → HOOK (lifecycle-driven, shell scripts, can block tool use)
│
├── Long-running, isolated, parallel work (background research, parallel reviews)?
│   └── → AGENT / SUBAGENT (spawned via Agent tool, isolated context)
│
├── Adding a new external tool or data source to Claude?
│   └── → MCP SERVER (extends Claude's tool palette)
│
├── Persistent facts across sessions (user prefs, project decisions, references)?
│   └── → MEMORY (markdown files in ~/.claude/projects/*/memory/)
│
├── Tracking steps in the current session only?
│   └── → TASK (TaskCreate/TaskUpdate — in-session checklist only)
│
├── Recording architectural decisions, progress, active focus this session?
│   └── → PLAN ARTIFACTS (active-context.md, decisions.md, progress.md in plans/)
│
├── Isolated branch/directory for parallel or risky work?
│   └── → WORKTREE (.trees/<name>/ via stack-create or git worktree)
│
├── Need to control what Claude can/cannot do?
│   └── → PERMISSIONS (settings.json allow/deny lists)
│
└── Tracking steps within THIS session only?
    ├── Is it a checklist (not spawning agents)?  → TodoWrite
    └── Is it spawning independent background agents?  → TaskCreate
```

---

## Primitive Reference Card

### Skill

| Property | Value |
|---|---|
| **File location** | `~/.dotfiles/ai/skills/<name>/SKILL.md` (symlinked to `~/.claude/skills/`) |
| **Invoked by** | User types `/<name>` or Skill tool is called by Claude |
| **Context** | Full Claude context — can use all MCP tools, Agent, Read/Write/Edit/Bash |
| **Lifecycle** | One-shot per invocation; runs inline in the active session |
| **Best for** | Workflows, automations, decisions that need Claude's reasoning + tools |
| **Not for** | Background/parallel work; use Agents for that |

**Anatomy of a SKILL.md:**
```markdown
---
name: <kebab-case>
description: >
  One-paragraph description. Includes: what it does, when to invoke it,
  and trigger keywords (so Claude can auto-invoke). Keep under 200 words.
version: 1.0.0
triggers:
  - keyword phrase one
  - keyword phrase two
---

# Skill Title

Brief one-liner on purpose.

## When to Use
[bullet conditions]

## Decision Tree (optional, for complex skills)
[ASCII tree]

## Instructions
[numbered steps, bash snippets, tool call patterns]

## Examples
[user input → action taken]

## Related Skills
[links to related skills]
```

**Auto-invoke rule:** Claude should auto-invoke a skill when the user's request matches a
trigger phrase AND the skill's description matches the task type. Do NOT force users to type
the slash command manually.

---

### Hook

| Property | Value |
|---|---|
| **File location** | `~/.dotfiles/.claude/hooks/<name>.sh` (or `.ts` via bun) |
| **Configured in** | `~/.claude/settings.json` → `hooks` → event → matcher → command |
| **Invoked by** | Claude Code lifecycle events (automatic, NOT user-triggered) |
| **Context** | Shell environment only — no Claude context, no MCP access |
| **Can block** | Yes — `PreToolUse` hooks that exit non-zero block the tool call |
| **Best for** | Enforcement, validation, logging, side effects on tool use |

**Hook lifecycle events:**

| Event | When | Common use |
|---|---|---|
| `SessionStart` | Session opens | Index codebase, load context, check pctx |
| `InstructionsLoaded` | CLAUDE.md read | Validate config, warm caches |
| `UserPromptSubmit` | User sends message | Sync indexes, inject hints, update collections |
| `PreToolUse` | Before any tool runs | **Block dangerous commands**, enforce patterns, gate writes |
| `PostToolUse` | After tool completes | Log output, track stats, update dashboards |
| `Notification` | Notification sent | Alert routing, tmux notifications |
| `PreCompact` | Before context compaction | Save session state to plans/ |
| `Stop` | Session ends | Write session summary, run completion checks |
| `WorktreeCreate` | Worktree created | Copy configs, open tmux windows |
| `WorktreeRemove` | Worktree removed | Clean up tmux, log worktree stats |

**Hook shell script template:**
```bash
#!/usr/bin/env bash
# Hook: <event>/<name>
# Purpose: <one-line description>
# Blocks: yes/no

set -euo pipefail

# Read tool input from stdin (PreToolUse/PostToolUse only)
TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')
TOOL_ARGS=$(echo "$TOOL_INPUT" | jq -r '.tool_input // {}')

# Guard: only apply to specific tools
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

# Logic here
COMMAND=$(echo "$TOOL_ARGS" | jq -r '.command // empty')

# Block with non-zero exit + message to stderr
if echo "$COMMAND" | grep -q "dangerous-pattern"; then
  echo "BLOCKED: reason" >&2
  exit 2  # exit 2 = block with message
fi

exit 0  # allow
```

**Settings.json hook registration:**
```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "bash -lc 'bash \"$HOME/.dotfiles/.claude/hooks/my-hook.sh\"'"
      }
    ]
  }
]
```

---

### Agent / SubAgent

| Property | Value |
|---|---|
| **Invoked by** | `Agent(subagent_type="...", prompt="...")` tool call |
| **Context** | Fresh isolated context — no parent conversation history |
| **Runs** | Foreground (blocks parent) or background (parallel) |
| **Best for** | Parallel work, context isolation, long research tasks |
| **Not for** | In-session state tracking (use Tasks); user-triggered flows (use Skills) |

**Available subagent types (this installation):**

| Type | Best for |
|---|---|
| `general-purpose` | Multi-step research, code search, complex tasks |
| `Explore` | Quick codebase exploration, file/keyword search |
| `Plan` | Implementation planning, architectural design |
| `claude-code-guide` | Claude Code API/SDK/feature questions |
| `mcp_config_manager` | JSON config manipulation across AI tools |

**Foreground vs Background:**
```
Need result before continuing?  → foreground (default)
Can proceed while it runs?      → background (run_in_background: true)
Need parallel execution?        → launch MULTIPLE agents in ONE message
```

**Agent prompt template:**
```
You are a [role] agent handling [task].
Context: [what the parent agent knows]
Task: [specific, bounded instructions]
Output: [expected format / what to return]
Do NOT: [explicit constraints]
```

**Team agents** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`):
- Agents can be named and messaged via `SendMessage(to: "agent-name")`
- Use for coordinator/worker patterns in complex pipelines

---

### MCP Server

| Property | Value |
|---|---|
| **Configured in** | `settings.json` → `mcpServers` OR `.mcp.json` (project-local) |
| **Exposes** | Tools, resources, prompts to Claude's tool palette |
| **Types** | stdio (process), sse (HTTP server) |
| **Best for** | External APIs, databases, specialized tool domains |

**Registration in settings.json:**
```json
"mcpServers": {
  "my-server": {
    "command": "node",
    "args": ["/path/to/server.js"],
    "env": { "API_KEY": "${env:MY_API_KEY}" }
  }
}
```

**Project-local `.mcp.json`** (checked into repo):
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

### Permissions

| Property | Value |
|---|---|
| **Configured in** | `~/.claude/settings.json` → `permissions.allow` / `permissions.deny` |
| **Scope** | Global (settings.json) or project-local (`.claude/settings.local.json`) |
| **Pattern syntax** | `ToolName(glob)` — e.g. `Bash(rm -rf *)`, `Read(./.env)`, `mcp__*__*` |
| **Best for** | Blocking destructive commands, protecting secrets, restricting tool scope |

**Common patterns:**
```json
"deny": [
  "Bash(rm -rf *)",        // destructive shell
  "Bash(sudo *)",           // privilege escalation
  "Read(./.env)",           // secret files
  "Edit(./secrets/**)"     // secret directories
],
"allow": [
  "mcp__*__*",             // all MCP tools
  "Bash(*)"                // all bash (override deny with specific deny rules)
]
```

**`defaultMode`**: `acceptEdits` (auto-approve edits) | `default` (prompt for each) | `bypassPermissions` (no prompts)

---

### TodoWrite vs TaskCreate — Critical Distinction

| | TodoWrite | TaskCreate |
|---|---|---|
| **What it creates** | In-session checklist items | Background agent tasks |
| **Who executes** | Claude (current session) | Spawned background agents |
| **Visibility** | Progress shown in current chat | Tracked via TaskList/TaskGet |
| **Use for** | Step-by-step implementation tracking | Parallel/background work delegation |
| **The RULE** | 3+ step tasks → use TodoWrite FIRST | Multi-agent pipelines only |

**Never use TaskCreate as a progress checklist.** It spawns agents. Use TodoWrite for that.

---

### Memory

| Property | Value |
|---|---|
| **Location** | `~/.claude/projects/<project-slug>/memory/` |
| **Format** | Markdown files with YAML frontmatter (`name`, `description`, `type`) |
| **Types** | `user`, `feedback`, `project`, `reference` |
| **Indexed by** | `MEMORY.md` (one-line entries, max 200 lines) |
| **Best for** | Cross-session facts: user preferences, project decisions, external references |
| **Not for** | In-session state (use Tasks/Plans); code patterns (read from codebase) |

---

## SDLC Role → Primitive Mapping

| Role | Primary Primitives | Use Pattern |
|---|---|---|
| **Developer** | Skills, Agents, Plans | stack-create + smart-commit + stack-pr |
| **QA Engineer** | Skills (autoresearch:fix), Agents (test runners), Hooks (PostToolUse test gate) | autoresearch Role=QA for red-phase tests |
| **Tech Lead** | Skills (bmad-custom-pr-review), Agents (parallel reviews), Memory (project decisions) | stack-aware PR review + ADL decisions.md |
| **Architect** | Skills (autoresearch:predict, autoresearch:learn), Agents (Plan type), Plans | RFC drafting, fitness functions, security audits |
| **DevOps** | Hooks (all lifecycle events), MCP Servers (infra APIs), Settings (permissions) | CI gates, deployment checks, credential safety |
| **PM / Analyst** | Skills (daily standup, reporting), Memory (project context), QMD search | Insights from activtrak, OKRs, cross-notebook query |

---

## Creation Workflows

### Creating a Skill

1. **Clarify**: What user action triggers it? What tools does it need? What's the output?
2. **Check for overlap**: `Glob("~/.dotfiles/ai/skills/*/SKILL.md")` — does a similar skill exist?
3. **Write the file**: `~/.dotfiles/ai/skills/<name>/SKILL.md` using the Anatomy template above
4. **Symlink** (if not auto-linked): `ln -s ~/.dotfiles/ai/skills/<name> ~/.claude/skills/<name>`
5. **Register triggers**: Ensure the CLAUDE.md `Multi-Model Routing` section routes to it if it's a model-delegation skill
6. **Test**: Invoke via `/<name>` in a fresh session

### Creating a Hook

1. **Pick the right event**: Use the hook lifecycle table above
2. **Determine blocking vs observing**: PreToolUse = can block; PostToolUse = observe only
3. **Write the script**: Use the shell template above. Validate jq parsing.
4. **Register in settings.json**: Add matcher + command under the correct event
5. **Test**: Trigger the event, check `~/.claude/logs/` or stderr for output
6. **Safety check**: Ensure `exit 0` on all non-matching paths to avoid accidental blocking

### Creating a SubAgent

1. **Define isolation boundary**: What context does the agent need? What should it NOT see?
2. **Write the prompt**: Be explicit about task, output format, constraints
3. **Choose foreground vs background**: Does the parent need the result before continuing?
4. **Declare subagent_type**: Match to the table above; use `general-purpose` when unsure
5. **Handle output**: Agents return a single message — parse it in the parent context

### Creating an MCP Server

1. **Identify the capability gap**: What tool does Claude need that doesn't exist?
2. **Choose transport**: stdio (local process) or sse (remote HTTP)
3. **Implement**: Follow MCP spec — expose `tools`, `resources`, or `prompts`
4. **Register**: Add to `settings.json` mcpServers (global) or `.mcp.json` (project)
5. **Load tools**: Use `ToolSearch(query: "select:mcp__<server>__<tool>")` before first use

---

## Common Mistakes & Anti-Patterns

| Anti-pattern | Correct approach |
|---|---|
| Using a Hook when you want a Skill | Hooks run shell only, no Claude reasoning. Use a Skill for anything needing LLM judgment. |
| Using a Skill when you want a Hook | Skills require user invocation. Use a Hook for automatic enforcement. |
| Using TaskCreate for parallel work | TaskCreate spawns background agents, not a checklist. Use TodoWrite for in-session tracking. |
| Putting session state in Memory | Memory is cross-session. Use Plans (active-context.md, progress.md) for current-session state. |
| Creating a new Skill for a one-off task | One-off tasks belong in the conversation, not a Skill. Skills are for repeated, invocable workflows. |
| Long Skill that does everything | Compose Skills — a top-level Skill can invoke sub-Skills. Keep each focused. |
| Hardcoding paths in hooks | Use `$HOME` not `/Users/name/`. Hooks must work for all users/environments. |
| PreToolUse hook that always blocks | Always `exit 0` on non-matching patterns. Accidental blanket blocking breaks the session. |

---

## Instructions

When this skill is invoked:

1. **Identify the goal**: What behavior or automation is the user trying to create?
2. **Run the Decision Tree** above — determine the correct primitive
3. **Ask one clarifying question if needed** (trigger conditions, tool requirements, output format)
4. **Create the artifact** using the creation workflow for that primitive type
5. **Register it** (symlink skills, update settings.json for hooks, etc.)
6. **Confirm with the user**: Show the file path and a one-line summary of what was created

If the user asks "which primitive should I use for X":
- Walk through the Decision Tree explicitly
- Explain the trade-offs (skill vs hook, agent vs task, memory vs plan)
- Recommend ONE option with a one-sentence justification

---

## Related Skills

- **skill-creator**: Claude Plugins official skill-creator (plugin-managed)
- **autoresearch**: Autonomous metric optimization loop (uses Agents + Hooks)
- **stack-create**: Worktree + stacked branch creation
- **explore**: Codebase navigation (uses pctx/Serena agents)
- **update-config**: Configure settings.json (hooks, permissions, MCP)
