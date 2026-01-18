# Claude Skills Integration with Charcoal + Worktrees

## Overview

Your Claude Skills are **fully integrated** with the Charcoal + Worktrees system. When you interact with Claude Code (the desktop app), it will automatically use these skills to help you manage your PR stack with full worktree support.

## How It Works

### 1. Skill Detection

When you say something like:
- "Create a worktree for fixing db issues"
- "Navigate to the parent branch"
- "Show me my PR stack"

Claude Code **automatically detects** which skill to use based on:
- **Skill descriptions** in the YAML frontmatter
- **Keywords** in your request
- **Context** of your current work

### 2. Skill Execution

Claude then:
1. Reads the skill instructions
2. Parses your request
3. Executes the appropriate `.claude/scripts/stack` command
4. Reports the results back to you

### 3. Worktree Awareness

All skills are now **worktree-aware**, meaning they:
- Detect if you're working with worktrees
- Provide worktree-specific guidance
- Use worktree-aware commands
- Show worktree locations in output

## Your Updated Skills

### 1. `stack-create` - Create Stacked Branches

**Location:** `.claude/skills/stack-create/SKILL.md`

**What it does:**
- Creates new stacked branches
- Optionally creates worktrees
- Tracks branches in Charcoal
- Copies IDE configurations

**Example interactions:**

```
You: "Create a worktree for the API feature on top of main"

Claude: I'll create a stacked branch with a worktree for you.
        
        [Executes: .claude/scripts/stack create feature/api main --worktree]
        
        ✅ Created worktree: .trees/api
        📂 Path: /path/to/repo/.trees/api
        🌿 Branch: feature/api (Base: main)
        🔗 Tracked in Charcoal
        
        You can now:
        1. cd .trees/api
        2. Start developing
        3. Use 'stack up/down' for navigation
```

```
You: "Create stacked worktrees for database, API, and UI"

Claude: I'll create three stacked branches with worktrees for parallel development.
        
        [Executes:]
        .claude/scripts/stack create feature/database main --worktree
        .claude/scripts/stack create feature/api feature/database --worktree
        .claude/scripts/stack create feature/ui feature/api --worktree
        
        ✅ Created 3 worktrees:
        - .trees/database (feature/database)
        - .trees/api (feature/api)
        - .trees/ui (feature/ui)
        
        All tracked in Charcoal! You can work on all three in parallel.
```

### 2. `stack-navigate` - Navigate Between Branches

**Location:** `.claude/skills/stack-navigate/SKILL.md`

**What it does:**
- Navigates to parent/child branches
- Detects worktrees automatically
- Provides cd commands for worktrees
- Suggests creating worktrees if missing

**Example interactions:**

```
You: "Go to the parent branch"

Claude: I'll navigate to the parent branch for you.
        
        [Executes: .claude/scripts/stack up]
        
        ℹ️  Navigating to worktree: .trees/api
        cd /path/to/repo/.trees/api
        
        To automatically navigate, use:
        eval $(.claude/scripts/stack up)
        
        Or set up an alias:
        alias stup='eval $(~/.claude/scripts/stack up)'
```

```
You: "I'm in the UI worktree, take me down to the next branch"

Claude: [Executes: .claude/scripts/stack down]
        
        ℹ️  Navigating to worktree: .trees/polish
        cd /path/to/repo/.trees/polish
```

### 3. `stack-status` - View Stack Status

**Location:** `.claude/skills/stack-status/SKILL.md`

**What it does:**
- Shows branch hierarchy
- Displays worktree locations
- Shows PR status
- Visualizes dependencies

**Example interactions:**

```
You: "Show me my PR stack"

Claude: Here's your current PR stack:
        
        [Executes: .claude/scripts/stack status]
        
        ╔════════════════════════════════════════════════════════╗
        ║         STACK STATUS (with Worktrees)                  ║
        ╚════════════════════════════════════════════════════════╝
        
        main
        ├── feature/database [WT: .trees/database]
        │   └── feature/api [WT: .trees/api]
        │       └── feature/ui [WT: .trees/ui]
        └── hotfix/security
        
        You have 3 branches with worktrees for parallel development!
```

```
You: "Which branches have worktrees?"

Claude: [Executes: .claude/scripts/stack status]
        
        Based on your stack, these branches have worktrees:
        - feature/database → .trees/database
        - feature/api → .trees/api
        - feature/ui → .trees/ui
        
        hotfix/security has no worktree (only in main repo).
```

### 4. Other Skills

**`stack-pr`** - Create PRs (works from any worktree)
**`stack-update`** - Update stack after merge (syncs worktrees)
**`stack-merge`** - Merge PRs (updates dependent worktrees)

## Complete Conversation Examples

### Example 1: Setting Up Parallel Development

```
You: "I need to work on three features in parallel: database, API, and UI. 
     Each one depends on the previous one."

Claude: I'll set up a stacked PR workflow with worktrees for parallel development.
        
        [Executes:]
        .claude/scripts/stack create feature/database main --worktree
        .claude/scripts/stack create feature/api feature/database --worktree
        .claude/scripts/stack create feature/ui feature/api --worktree
        
        ✅ Created your parallel development setup:
        
        main
        ├── feature/database [WT: .trees/database]
            └── feature/api [WT: .trees/api]
                └── feature/ui [WT: .trees/ui]
        
        You can now:
        1. Open 3 terminal windows
        2. Terminal 1: cd .trees/database
        3. Terminal 2: cd .trees/api
        4. Terminal 3: cd .trees/ui
        5. Work on all three simultaneously!
        
        Navigation:
        - Use 'eval $(stack up)' to go to parent
        - Use 'eval $(stack down)' to go to child
        - Use 'stack status' to see the full picture
        
        When you're ready to create PRs:
        stack pr feature/database main "Add database layer"
        stack pr feature/api feature/database "Add API layer"
        stack pr feature/ui feature/api "Add UI layer"

You: "Great! Now show me the status"

Claude: [Executes: .claude/scripts/stack status]
        
        Here's your current setup:
        [Shows full stack with worktree locations]

You: "I'm in the UI worktree. Take me to the API worktree"

Claude: [Executes: .claude/scripts/stack up]
        
        cd /path/to/repo/.trees/api
        
        [You can copy this command or use: eval $(stack up)]
```

### Example 2: Adding Worktree to Existing Branch

```
You: "I have a branch called feature/api but no worktree. Can you add one?"

Claude: I'll add a worktree for your existing feature/api branch.
        
        [Executes: .claude/scripts/stack worktree-add feature/api]
        
        ✅ Created worktree: .trees/api
        📂 Path: /path/to/repo/.trees/api
        🌿 Branch: feature/api
        
        The branch is already tracked in Charcoal, so navigation will work!
        
        To navigate there:
        cd .trees/api

You: "Perfect! Now show me which branches have worktrees"

Claude: [Executes: .claude/scripts/stack status]
        
        Here's your stack with worktree information:
        [Shows branches with [WT: path] markers]
```

### Example 3: Restacking After Merge

```
You: "The database PR was merged. I need to rebase the API and UI branches"

Claude: I'll restack your branches and sync all worktrees.
        
        [Executes: .claude/scripts/stack restack]
        
        ℹ️  Using Charcoal to restack branches...
        ✅ Stack rebased successfully
        ℹ️  Syncing worktrees...
        ℹ️  Syncing worktree: .trees/api (feature/api)
        ℹ️  Syncing worktree: .trees/ui (feature/ui)
        ✅ Metadata synced
        
        All done! Your worktrees are now up-to-date with the merged changes.
        
        What happened:
        1. feature/api rebased onto new main (includes merged database)
        2. feature/ui rebased onto new feature/api
        3. Both worktrees notified of changes
        
        You can continue working in your worktrees without any disruption!
```

## How Claude Understands Your Intent

### Keywords Claude Recognizes

**For creating branches/worktrees:**
- "create", "make", "set up", "initialize"
- "worktree", "parallel", "simultaneously"
- "stacked", "on top of", "based on"

**For navigation:**
- "go to", "navigate to", "switch to", "move to"
- "parent", "child", "up", "down"
- "previous", "next"

**For status:**
- "show", "display", "view", "list"
- "stack", "branches", "hierarchy"
- "status", "where am I"

**For worktree management:**
- "add worktree", "create worktree"
- "remove worktree", "delete worktree"
- "list worktrees", "show worktrees"

### Context Awareness

Claude also understands context:
- If you mention "parallel development" → Suggests worktrees
- If you're in a worktree → Uses worktree-aware commands
- If you mention multiple features → Suggests stacked worktrees
- If you mention navigation → Checks for worktrees first

## Skill Chaining

Claude can chain multiple skills together:

```
You: "Set up parallel development for API and UI, then show me the status"

Claude: [Uses stack-create skill twice, then stack-status skill]
        
        1. Created feature/api with worktree
        2. Created feature/ui with worktree
        3. Here's your stack:
           [Shows status with worktree locations]
```

## Configuration

### Skill Location

All skills are in: `.claude/skills/`

```
.claude/skills/
├── stack-create/
│   └── SKILL.md
├── stack-navigate/
│   └── SKILL.md
├── stack-status/
│   └── SKILL.md
├── stack-pr/
│   └── SKILL.md
├── stack-update/
│   └── SKILL.md
└── stack-merge/
    └── SKILL.md
```

### Claude Settings

Your Claude settings (`.claude/settings.json`) should have skills enabled:

```json
{
  "enabledPlugins": {
    "document-skills@anthropic-agent-skills": true
  }
}
```

### Skill Updates

Skills are automatically loaded by Claude Code. When you update a skill:
1. Save the SKILL.md file
2. Claude Code picks up changes automatically
3. No restart needed!

## Benefits of Skills Integration

### 1. Natural Language Interface

Instead of remembering commands:
```bash
.claude/scripts/stack create feature/api main --worktree
```

You can just say:
```
"Create a worktree for the API feature"
```

### 2. Context-Aware Suggestions

Claude suggests the best approach:
- Recommends worktrees for parallel work
- Suggests navigation commands
- Offers to create missing worktrees

### 3. Error Handling

If something goes wrong, Claude:
- Explains the error
- Suggests fixes
- Offers alternatives

### 4. Workflow Guidance

Claude guides you through complex workflows:
- Setting up parallel development
- Creating stacked PRs
- Restacking after merges
- Managing worktrees

## Testing Your Skills

### Test in Claude Code

1. Open Claude Code
2. Navigate to your repo
3. Try these prompts:

```
"Create a worktree for testing"
"Show me my PR stack"
"Navigate to the parent branch"
"Add a worktree for my feature/api branch"
```

### Check Skill Detection

Claude will show you which skill it's using:
```
[Using skill: stack-create]
[Using skill: stack-navigate]
[Using skill: stack-status]
```

## Troubleshooting

### Skill Not Detected

**Problem:** Claude doesn't recognize your request.

**Solution:**
- Use clearer keywords ("create worktree" instead of "make a thing")
- Be more specific ("navigate to parent" instead of "go there")
- Check skill descriptions match your intent

### Command Fails

**Problem:** Skill executes but command fails.

**Solution:**
- Check if Charcoal is installed: `gt --version`
- Check if initialized: `.claude/scripts/stack init`
- Check if in git repo: `git status`

### Worktree Not Detected

**Problem:** Skill doesn't show worktree information.

**Solution:**
- Verify worktree exists: `git worktree list`
- Check if created with `--worktree` flag
- Try: `.claude/scripts/stack status`

## Advanced: Customizing Skills

You can customize skills for your workflow:

### Add Custom Keywords

Edit `.claude/skills/stack-create/SKILL.md`:

```markdown
## When to Use

Use this skill when the user wants to:
- Create a new branch
- **YOUR CUSTOM KEYWORD HERE**
```

### Add Custom Examples

```markdown
## Examples

User: "YOUR CUSTOM PROMPT"
Action: `.claude/scripts/stack create ...`
```

### Add Custom Instructions

```markdown
## Instructions

1. Parse the user's request
2. **YOUR CUSTOM STEP**
3. Execute command
```

## Summary

Your Claude Skills provide a **natural language interface** to the Charcoal + Worktrees integration:

✅ **Natural prompts** instead of memorizing commands
✅ **Context-aware** suggestions and guidance
✅ **Worktree-aware** operations throughout
✅ **Error handling** and helpful feedback
✅ **Workflow guidance** for complex operations

Just talk to Claude naturally, and it will use the right skills to help you manage your PR stack with full Charcoal capabilities and worktree support!

---

**Try it now in Claude Code:**
```
"Create stacked worktrees for database, API, and UI features"
```
