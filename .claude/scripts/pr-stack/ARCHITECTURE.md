# Architecture: Charcoal + Worktrees Integration

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Git Repository                          │
│                                                                 │
│  ┌──────────────┐                                              │
│  │  Main Repo   │                                              │
│  │  (master)    │                                              │
│  └──────────────┘                                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    .git/ (Shared)                         │ │
│  │                                                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐ │ │
│  │  │ .gt/        │  │ pr-stack-   │  │ worktrees/       │ │ │
│  │  │ (Charcoal)  │  │ info        │  │ (Git metadata)   │ │ │
│  │  └─────────────┘  └─────────────┘  └──────────────────┘ │ │
│  │                                                            │ │
│  │  All worktrees share this metadata!                       │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ .trees/api/  │  │ .trees/ui/   │  │ .trees/test/ │        │
│  │ (Worktree)   │  │ (Worktree)   │  │ (Worktree)   │        │
│  │              │  │              │  │              │        │
│  │ feature/api  │  │ feature/ui   │  │ feature/test │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Creating a Worktree with Charcoal Tracking

```
User Command:
  stack create feature/api main --worktree

       │
       ▼
┌──────────────────┐
│  create-stack.sh │  ← Native script creates worktree
└────────┬─────────┘
         │
         ├─► git worktree add -b feature/api .trees/api main
         │   (Creates isolated directory)
         │
         ├─► Copy configs (.env, .vscode, .mcp.json, etc.)
         │   (Each worktree gets own IDE settings)
         │
         ├─► Store in .git/pr-stack-info
         │   feature/api:main:timestamp
         │
         └─► gt branch track feature/api --parent main
             (Charcoal now knows about this branch!)

Result:
  ✅ Worktree at .trees/api/
  ✅ Tracked in Charcoal
  ✅ Can use navigation and restacking
```

### 2. Navigation (Worktree-Aware)

```
User Command (from .trees/ui/):
  stack up

       │
       ▼
┌──────────────────────┐
│ wt_charcoal_up()     │  ← Worktree-aware wrapper
└──────────┬───────────┘
           │
           ├─► Get current branch: feature/ui
           │
           ├─► Query Charcoal: gt stack --json
           │   Find parent: feature/api
           │
           ├─► Check: Does feature/api have a worktree?
           │   └─► get_worktree_path("feature/api")
           │       └─► git worktree list --porcelain
           │           └─► Returns: .trees/api
           │
           └─► Output: cd .trees/api

User executes:
  eval $(stack up)
  → Changes directory to .trees/api/
```

### 3. Restacking (All Worktrees)

```
User Command:
  stack restack

       │
       ▼
┌──────────────────────┐
│ wt_charcoal_restack()│
└──────────┬───────────┘
           │
           ├─► cd <main-repo>
           │   gt restack
           │   (Charcoal rebases all branches)
           │
           ├─► For each worktree:
           │   │
           │   ├─► cd .trees/api/
           │   │   git fetch origin feature/api
           │   │   Check if behind upstream
           │   │
           │   ├─► cd .trees/ui/
           │   │   git fetch origin feature/ui
           │   │   Check if behind upstream
           │   │
           │   └─► cd .trees/test/
           │       git fetch origin feature/test
           │       Check if behind upstream
           │
           └─► sync_charcoal_to_native()
               (Update .git/pr-stack-info)

Result:
  ✅ All branches rebased
  ✅ All worktrees notified
  ✅ Metadata synced
```

## Component Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Interface                             │
│                                                                 │
│  .claude/scripts/stack  ←─── Claude Skills                     │
│  (Main CLI)                  (stack-create, etc.)              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Layer                            │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │ worktree-charcoal.sh │  │ charcoal-compat.sh   │           │
│  │                      │  │                      │           │
│  │ • is_in_worktree()   │  │ • charcoal_init()    │           │
│  │ • wt_charcoal_up()   │  │ • sync_metadata()    │           │
│  │ • wt_charcoal_down() │  │ • charcoal_version() │           │
│  │ • wt_charcoal_restack│  │                      │           │
│  │ • wt_add_for_branch()│  │                      │           │
│  └──────────────────────┘  └──────────────────────┘           │
│                                                                 │
│  ┌──────────────────────┐                                      │
│  │ validation.sh        │                                      │
│  │ • print_info()       │                                      │
│  │ • print_error()      │                                      │
│  │ • get_repo_root()    │                                      │
│  └──────────────────────┘                                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Native Scripts                             │
│                                                                 │
│  • create-stack.sh    (Worktree creation + config copying)     │
│  • create-pr.sh       (Azure DevOps PR creation)               │
│  • update-stack.sh    (Update after merge)                     │
│  • list-stack.sh      (Display stack status)                   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Tools                               │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   git    │  │ Charcoal │  │   jq     │  │  gh CLI  │      │
│  │          │  │   (gt)   │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## State Management

### Charcoal State (`.git/.gt/`)

```json
{
  "branches": [
    {
      "name": "feature/api",
      "parent": "main",
      "children": ["feature/ui"]
    },
    {
      "name": "feature/ui",
      "parent": "feature/api",
      "children": ["feature/test"]
    },
    {
      "name": "feature/test",
      "parent": "feature/ui",
      "children": []
    }
  ]
}
```

### Native State (`.git/pr-stack-info`)

```
feature/api:main:1705881234
feature/ui:feature/api:1705881245
feature/test:feature/ui:1705881256
```

### Git Worktree State (`.git/worktrees/`)

```
.git/worktrees/
├── api/
│   ├── HEAD          → refs/heads/feature/api
│   ├── gitdir        → /path/to/.trees/api/.git
│   └── ...
├── ui/
│   ├── HEAD          → refs/heads/feature/ui
│   ├── gitdir        → /path/to/.trees/ui/.git
│   └── ...
└── test/
    ├── HEAD          → refs/heads/feature/test
    ├── gitdir        → /path/to/.trees/test/.git
    └── ...
```

## Key Design Decisions

### 1. Why Track Branches in Charcoal After Worktree Creation?

**Problem:** Charcoal's `gt branch create` manages checkouts, which conflicts with worktree creation.

**Solution:** 
- Use native `git worktree add` to create the worktree
- Then use `gt branch track` to register it in Charcoal
- This gives us both: isolated directory + Charcoal tracking

### 2. Why Output `cd` Commands Instead of Changing Directory?

**Problem:** Bash scripts run in subshells and can't change the parent shell's directory.

**Solution:**
- Output the `cd` command as text
- User can copy-paste or use `eval $(stack up)`
- Or create shell aliases that wrap with `eval`

### 3. Why Sync Worktrees After Restack?

**Problem:** After `gt restack`, branches are rebased but worktrees might not be aware.

**Solution:**
- Run `git fetch` in each worktree after restack
- Notify user if worktree is behind
- User can then `git pull --rebase` if needed

### 4. Why Keep Both Charcoal and Native Metadata?

**Problem:** Azure DevOps scripts need `.git/pr-stack-info`, Charcoal uses `.git/.gt/`.

**Solution:**
- Maintain both formats
- Sync bidirectionally
- Each system can work independently if needed

## Error Handling

### Scenario: Parent Branch Has No Worktree

```
User in .trees/ui/ runs: stack up
Parent is feature/api (no worktree)

Output:
  ⚠️  Parent branch feature/api has no worktree
  Options:
    1. Create worktree: ./scripts/stack worktree-add feature/api
    2. Navigate in main repo: (cd /path/to/main && gt up)
```

### Scenario: Worktree Out of Sync

```
After restack, .trees/ui/ is behind

Output:
  ℹ️  Syncing worktree: .trees/ui (feature/ui)
  ⚠️  Worktree .trees/ui is behind by 3 commits
      Run: cd .trees/ui && git pull --rebase
```

### Scenario: Charcoal Not Initialized

```
User runs: stack up

Output:
  ❌ Charcoal not initialized. Run: ./scripts/stack init
```

## Performance Considerations

### Worktree Creation
- **Fast**: Native git operation
- **Config copying**: Only copies untracked files
- **Charcoal tracking**: Single `gt branch track` call

### Navigation
- **Instant**: Just outputs a cd command
- **No checkout**: Doesn't touch working directory
- **JSON parsing**: Uses `jq` if available, falls back to grep

### Restacking
- **Main operation**: Charcoal handles the rebasing
- **Worktree sync**: Parallel fetches (could be optimized)
- **Metadata sync**: Single file write

## Future Optimizations

1. **Parallel Worktree Sync**: Use background jobs to fetch in all worktrees simultaneously
2. **Caching**: Cache worktree paths to avoid repeated `git worktree list` calls
3. **Smart Sync**: Only sync worktrees that are affected by the restack
4. **Auto-pull**: Option to automatically pull in worktrees after restack
5. **Worktree Templates**: Pre-configured worktree setups for common workflows
