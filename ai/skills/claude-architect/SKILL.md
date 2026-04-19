---
name: claude-architect
description: >
  Creates, designs, and registers Claude Code primitives — Skills, Hooks, Agents, MCP Servers,
  Memory, Permissions, and Worktrees. Use this whenever someone asks to control or extend Claude Code
  behavior, choose between skills/hooks/agents/MCP, create a slash command, automate Claude behavior,
  add permissions, block Claude actions, or explain TodoWrite vs TaskCreate. Do not use for git hooks,
  GitHub Actions, external schedulers, editor extensions, or general bash scripting unrelated to Claude.
version: 2.1.0
triggers:
  - create a skill
  - create skill
  - new skill
  - add a hook
  - create a hook
  - is that a hook
  - design a subagent
  - create subagent
  - create agent
  - build a command
  - new command
  - create slash command
  - set up mcp
  - add mcp server
  - give claude access
  - i want claude to be able to call
  - i want claude to automatically
  - can i make it automatic
  - make it automatic somehow
  - automate when
  - which primitive
  - what primitive
  - should i use a skill or
  - should i use a hook or
  - which is better a skill or
  - which is better for blocking
  - difference between agent and subagent
  - difference between agent vs subagent
  - agent vs subagent vs skill
  - block claude from
  - prevent claude from
  - claude architect
  - configure permissions
  - add permission
  - todowrite vs task
  - when to use todowrite
---

# Claude Architect

**Builds Claude Code primitives.** When invoked, give a SHORT decision + build the artifact immediately. Do NOT produce a reference-card dump. The user wants the thing built, not a tutorial.

---

## How to respond when invoked

1. **One sentence**: state which primitive and why
2. **Build it**: write the file / snippet / config — no preamble
3. **Register it**: symlink, settings.json entry, etc.
4. **Confirm**: one line — path created + what it does

If the user asks "which primitive should I use?", pick one and explain in 2-3 sentences. Do not reproduce the full decision tree.

---

## Decision Tree — Pick the primitive

```
What are you automating?
│
├── User runs a slash command to trigger it?              → SKILL
├── Fires automatically on a tool call / session event?  → HOOK
├── Long-running, parallel, or isolated work?            → AGENT / SUBAGENT
├── Adding an external tool or API to Claude?            → MCP SERVER
├── Persistent facts that survive across sessions?       → MEMORY
├── Control what Claude can/cannot do?                   → PERMISSIONS
├── Isolated branch/directory for parallel work?         → WORKTREE
├── Track steps in THIS session (checklist)?             → TodoWrite
└── Spawn independent background agent tasks?            → TaskCreate
```

**Skill vs Hook — the most common confusion:**
- **Skill**: user must invoke it (`/skill-name`). Use when judgment or tools are needed.
- **Hook**: fires automatically on lifecycle events. Use when enforcement or silent logging is needed. No Claude context — shell only.

**TodoWrite vs TaskCreate — critical distinction:**
- **TodoWrite**: in-session checklist Claude executes itself. Use for 3+ step tasks.
- **TaskCreate**: spawns background agents. Never use as a progress tracker.

---

## Creation Checklists

### Skill
- [ ] Write `~/.dotfiles/ai/skills/<name>/SKILL.md` (frontmatter: name, description with triggers, version, triggers list)
- [ ] Description must be "pushy" — include "use this whenever..." so Claude auto-invokes
- [ ] Body: When to Use → Instructions → Examples → Related Skills
- [ ] Symlink: `ln -sf ~/.dotfiles/ai/skills/<name> ~/.claude/skills/<name>`
- [ ] Test: invoke via `/<name>` in a new session

### Hook
- [ ] Choose the right event (see table in `references/primitives.md`)
- [ ] Write `~/.dotfiles/.claude/hooks/<name>.sh`
- [ ] Script MUST `exit 0` on all non-matching paths — never accidentally block unrelated tools
- [ ] PreToolUse = can block (exit 2); PostToolUse = observe only (always exit 0)
- [ ] For pattern matching: use word boundaries (`\b`) to avoid false positives (e.g., `\b(main|master)\b` not `(main|master)`)
- [ ] Make executable: `chmod +x ~/.dotfiles/.claude/hooks/<name>.sh`
- [ ] Register in `~/.claude/settings.json` under the correct event with matcher
- [ ] Test: trigger the matching case AND verify a non-matching command still works

### SubAgent
- [ ] Define what the agent needs to know (context) and what it must NOT see (isolation)
- [ ] Write a prompt: role + task + output format + constraints
- [ ] Foreground if parent needs the result; background if parallel
- [ ] Use `run_in_background: true` + name the agent for `SendMessage` coordination

### MCP Server
- [ ] Identify the tool gap — what can't Claude do with existing tools?
- [ ] Register in `~/.claude/settings.json` → `mcpServers` (global) or `.mcp.json` (project)
- [ ] Tools must be loaded before use: `ToolSearch("select:mcp__<server>__<tool>")`

---

## Examples

**User:** "I want Claude to automatically log every file it reads to an audit log."
→ **Hook** (PostToolUse/Read — automatic, silent, no user invocation needed)
→ Write `~/.dotfiles/.claude/hooks/read-audit.sh`, register under PostToolUse with `"matcher": "Read"`

**User:** "Create a skill that runs a security scan on my Kubernetes manifests."
→ **Skill** (user-invoked, needs Claude's reasoning to parse YAML and produce a findings report)
→ Write `~/.dotfiles/ai/skills/k8s-security-audit/SKILL.md`, symlink to `~/.claude/skills/`

**User:** "Block Claude from pushing to main or master automatically."
→ **Hook** (PreToolUse/Bash — must block BEFORE execution, not after)
→ Write hook matching `git push.*\b(main|master)\b` (word boundaries prevent false positives like `main-feature`), exits 2 to block, exits 0 on non-match; `chmod +x` the script

**User:** "Should I use a skill or a hook to enforce commit message format?"
→ **Hook** (PreToolUse on Bash matching `git commit`) — automatic enforcement, no LLM needed
→ If the format check needs Claude's judgment (e.g., semantic quality), use a Skill instead

---

## SDLC Role Quick Map

| You are a... | Reach for... |
|---|---|
| Developer | Skills (stack-create, smart-commit, stack-pr), Plans |
| QA Engineer | Skills (autoresearch:fix Role=QA), Hooks (PostToolUse test gate) |
| Tech Lead | Skills (bmad-custom-pr-review), Agents (parallel reviews), Memory |
| Architect | Skills (autoresearch:predict/learn), Agents (Plan type), Plans |
| DevOps | Hooks (all lifecycle events), MCP Servers, Permissions |
| PM / Analyst | Skills (standup, reporting), Memory, QMD search |

---

## Reference

Full primitive reference (hook events, agent types, MCP config, memory format, permissions syntax):
→ See `references/primitives.md` — load it only when you need low-level details

**Anti-patterns to avoid:**
- Hook when you need LLM reasoning → use a Skill instead
- Skill for automatic enforcement → use a Hook instead
- PreToolUse hook that doesn't exit 0 on non-matching paths → breaks all other tool calls
- TaskCreate as a progress checklist → spawns agents, not a checklist (use TodoWrite)
- Putting dev credentials in base/ kustomize layer → use overlays per environment
