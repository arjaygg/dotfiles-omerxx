# Claude Skills Flow Diagram

## Complete System Architecture with Skills

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                            │
│                                                                     │
│  Natural Language:                                                  │
│  "Create stacked worktrees for API and UI"                         │
│  "Navigate to parent branch"                                        │
│  "Show me my PR stack"                                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CLAUDE CODE (AI)                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              Skill Detection & Selection                      │ │
│  │                                                                │ │
│  │  1. Parse user intent                                         │ │
│  │  2. Match keywords to skills                                  │ │
│  │  3. Select appropriate skill                                  │ │
│  │  4. Read skill instructions                                   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Available Skills:                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │stack-create  │  │stack-navigate│  │stack-status  │            │
│  │              │  │              │  │              │            │
│  │Create branch │  │Navigate      │  │Show stack    │            │
│  │+ worktree    │  │worktree-aware│  │+ worktrees   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │stack-pr      │  │stack-update  │  │stack-merge   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STACK CLI (Enhanced)                             │
│                    .claude/scripts/stack                            │
│                                                                     │
│  Commands:                                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ create <branch> [base] [--worktree]                          │ │
│  │ up / down                                                     │ │
│  │ restack                                                       │ │
│  │ status                                                        │ │
│  │ worktree-add / worktree-list / worktree-remove               │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Routes to:                                                         │
│  ┌────────────────────┐  ┌────────────────────┐                   │
│  │ Native Scripts     │  │ Integration Layer  │                   │
│  │ (create-stack.sh)  │  │ (worktree-charcoal)│                   │
│  └────────────────────┘  └────────────────────┘                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              WORKTREE-CHARCOAL INTEGRATION LAYER                    │
│              .claude/scripts/pr-stack/lib/                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ worktree-charcoal.sh                                         │ │
│  │                                                                │ │
│  │  • is_in_worktree()        - Detect worktree                 │ │
│  │  • get_worktree_path()     - Find worktree for branch        │ │
│  │  • wt_charcoal_up()        - Navigate to parent worktree     │ │
│  │  • wt_charcoal_down()      - Navigate to child worktree      │ │
│  │  • wt_charcoal_restack()   - Restack + sync worktrees        │ │
│  │  • wt_add_for_branch()     - Add worktree to existing branch │ │
│  │  • wt_stack_status()       - Show stack with worktree info   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ charcoal-compat.sh                                           │ │
│  │                                                                │ │
│  │  • charcoal_available()    - Check if Charcoal installed     │ │
│  │  • charcoal_initialized()  - Check if initialized            │ │
│  │  • sync_metadata()         - Sync Charcoal ↔ native          │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL TOOLS                                 │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   Git        │  │  Charcoal    │  │     jq       │            │
│  │              │  │   (gt)       │  │              │            │
│  │ • worktree   │  │ • branch     │  │ • JSON parse │            │
│  │ • branch     │  │ • stack      │  │              │            │
│  │ • rebase     │  │ • restack    │  │              │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SHARED METADATA                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ .git/.gt/    │  │ .git/        │  │ .git/        │            │
│  │ (Charcoal)   │  │ pr-stack-info│  │ worktrees/   │            │
│  │              │  │ (Native)     │  │ (Git)        │            │
│  │ Stack info   │  │ Stack info   │  │ Worktree     │            │
│  │ Parent/child │  │ PR metadata  │  │ locations    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  All shared across worktrees!                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      WORKTREES                                      │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ .trees/api/  │  │ .trees/ui/   │  │.trees/polish/│            │
│  │              │  │              │  │              │            │
│  │ feature/api  │  │ feature/ui   │  │feature/polish│            │
│  │              │  │              │  │              │            │
│  │ .git → main  │  │ .git → main  │  │ .git → main  │            │
│  │ .vscode/     │  │ .vscode/     │  │ .vscode/     │            │
│  │ .mcp.json    │  │ .mcp.json    │  │ .mcp.json    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  Each has own config, all share metadata!                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Example Flow: "Create stacked worktrees for API and UI"

```
Step 1: User Input
┌─────────────────────────────────────────────────────────────┐
│ User: "Create stacked worktrees for API and UI"            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 2: Claude Skill Detection
┌─────────────────────────────────────────────────────────────┐
│ Claude Code:                                                │
│ • Detects keywords: "create", "stacked", "worktrees"       │
│ • Matches to skill: stack-create                           │
│ • Reads: .claude/skills/stack-create/SKILL.md              │
│ • Parses: Need 2 branches with worktrees                   │
│ • Determines: feature/api (base: main)                     │
│              feature/ui (base: feature/api)                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 3: CLI Execution
┌─────────────────────────────────────────────────────────────┐
│ Executes:                                                   │
│ .claude/scripts/stack create feature/api main --worktree   │
│ .claude/scripts/stack create feature/ui feature/api --wt   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 4: Integration Layer (For each branch)
┌─────────────────────────────────────────────────────────────┐
│ For feature/api:                                            │
│ 1. git worktree add -b feature/api .trees/api main         │
│ 2. Copy configs (.env, .vscode, .mcp.json)                 │
│ 3. gt branch track feature/api --parent main               │
│ 4. Update .git/pr-stack-info                               │
│                                                             │
│ For feature/ui:                                             │
│ 1. git worktree add -b feature/ui .trees/ui feature/api    │
│ 2. Copy configs (.env, .vscode, .mcp.json)                 │
│ 3. gt branch track feature/ui --parent feature/api         │
│ 4. Update .git/pr-stack-info                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 5: Result
┌─────────────────────────────────────────────────────────────┐
│ Claude Reports:                                             │
│                                                             │
│ ✅ Created your parallel development setup:                │
│                                                             │
│ main                                                        │
│ └── feature/api [WT: .trees/api]                          │
│     └── feature/ui [WT: .trees/ui]                        │
│                                                             │
│ You can now:                                                │
│ • Terminal 1: cd .trees/api                                │
│ • Terminal 2: cd .trees/ui                                 │
│ • Use: stack up/down for navigation                        │
│ • Use: stack restack to rebase everything                  │
└─────────────────────────────────────────────────────────────┘
```

## Example Flow: "Navigate to parent branch"

```
Step 1: User Input (in .trees/ui/)
┌─────────────────────────────────────────────────────────────┐
│ User: "Navigate to parent branch"                          │
│ (Currently in: .trees/ui/)                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 2: Claude Skill Detection
┌─────────────────────────────────────────────────────────────┐
│ Claude Code:                                                │
│ • Detects keywords: "navigate", "parent"                   │
│ • Matches to skill: stack-navigate                         │
│ • Reads: .claude/skills/stack-navigate/SKILL.md            │
│ • Determines: Need to go up in stack                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 3: CLI Execution
┌─────────────────────────────────────────────────────────────┐
│ Executes:                                                   │
│ .claude/scripts/stack up                                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 4: Integration Layer (Worktree-Aware)
┌─────────────────────────────────────────────────────────────┐
│ wt_charcoal_up():                                          │
│ 1. Detect: Currently in worktree (.trees/ui/)             │
│ 2. Get current branch: feature/ui                          │
│ 3. Query Charcoal: Parent is feature/api                   │
│ 4. Check: Does feature/api have worktree?                  │
│    └─> Yes! At .trees/api                                  │
│ 5. Output: cd /path/to/repo/.trees/api                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 5: Result
┌─────────────────────────────────────────────────────────────┐
│ Claude Reports:                                             │
│                                                             │
│ ℹ️  Navigating to worktree: .trees/api                     │
│ cd /path/to/repo/.trees/api                                 │
│                                                             │
│ To automatically navigate, use:                             │
│ eval $(.claude/scripts/stack up)                           │
│                                                             │
│ Or set up an alias:                                         │
│ alias stup='eval $(~/.claude/scripts/stack up)'            │
└─────────────────────────────────────────────────────────────┘
```

## Example Flow: "Show me my PR stack"

```
Step 1: User Input
┌─────────────────────────────────────────────────────────────┐
│ User: "Show me my PR stack"                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 2: Claude Skill Detection
┌─────────────────────────────────────────────────────────────┐
│ Claude Code:                                                │
│ • Detects keywords: "show", "PR stack"                     │
│ • Matches to skill: stack-status                           │
│ • Reads: .claude/skills/stack-status/SKILL.md              │
│ • Determines: Need to display stack with worktree info     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 3: CLI Execution
┌─────────────────────────────────────────────────────────────┐
│ Executes:                                                   │
│ .claude/scripts/stack status                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 4: Integration Layer (Worktree-Aware)
┌─────────────────────────────────────────────────────────────┐
│ wt_stack_status():                                         │
│ 1. Get Charcoal stack: gt stack                            │
│ 2. For each branch:                                         │
│    • Check if has worktree: git worktree list              │
│    • Enhance output with [WT: path] marker                 │
│ 3. Get PR info from .git/pr-stack-info                     │
│ 4. Combine all information                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
Step 5: Result
┌─────────────────────────────────────────────────────────────┐
│ Claude Reports:                                             │
│                                                             │
│ ╔════════════════════════════════════════════════════════╗ │
│ ║         STACK STATUS (with Worktrees)                  ║ │
│ ╚════════════════════════════════════════════════════════╝ │
│                                                             │
│ main                                                        │
│ ├── feature/database [WT: .trees/database]                │
│ │   └── feature/api [WT: .trees/api]                     │
│ │       └── feature/ui [WT: .trees/ui]                   │
│ └── hotfix/security                                        │
│                                                             │
│ ════════════════════════════════════════════════════════   │
│                                                             │
│ Native Stack View (with PR info):                          │
│ feature/database → main (PR #123: Open)                   │
│ feature/api → feature/database (PR #124: Open)            │
│ feature/ui → feature/api (PR #125: Open)                  │
│ hotfix/security → main (PR #126: Merged)                  │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
Natural Language
       ↓
Claude Skills (AI understands intent)
       ↓
Stack CLI (Routes to correct handler)
       ↓
Integration Layer (Worktree-aware logic)
       ↓
External Tools (Git, Charcoal)
       ↓
Shared Metadata (Synced across worktrees)
       ↓
Worktrees (Isolated development environments)
```

## Key Integration Points

### 1. Skills → CLI
- Skills read instructions from `.claude/skills/*/SKILL.md`
- Execute commands via `.claude/scripts/stack`
- Report results back to user

### 2. CLI → Integration Layer
- CLI routes to `worktree-charcoal.sh` functions
- Integration layer provides worktree-aware logic
- Handles both worktree and non-worktree cases

### 3. Integration Layer → External Tools
- Uses `git worktree` for worktree management
- Uses `gt` (Charcoal) for stack management
- Syncs metadata between systems

### 4. Metadata → Worktrees
- All worktrees share `.git/.gt/` (Charcoal)
- All worktrees share `.git/pr-stack-info` (native)
- Each worktree has own configs (`.vscode`, `.mcp.json`)

## Benefits of This Architecture

1. **Separation of Concerns**
   - Skills: Natural language understanding
   - CLI: Command routing
   - Integration: Worktree-aware logic
   - Tools: Actual operations

2. **Flexibility**
   - Can use CLI directly or via skills
   - Can use with or without Charcoal
   - Can use with or without worktrees

3. **Maintainability**
   - Each layer has clear responsibility
   - Easy to update skills without changing CLI
   - Easy to update integration without changing skills

4. **User Experience**
   - Natural language interface (skills)
   - Command line interface (CLI)
   - Both work seamlessly together
