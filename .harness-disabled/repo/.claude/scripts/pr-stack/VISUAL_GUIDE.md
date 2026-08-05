# Visual Guide: Charcoal + Worktrees

## 🎯 The Problem

### Before: Choose One

```
┌─────────────────────────────────────────────────────────────┐
│                    Charcoal Only                            │
│                                                             │
│  ✅ Easy navigation (gt up/down)                           │
│  ✅ Automatic restacking                                   │
│  ✅ Visual stack display                                   │
│  ❌ Can't work on multiple branches simultaneously        │
│  ❌ Context switching required                            │
│  ❌ Single working directory                              │
└─────────────────────────────────────────────────────────────┘

                         OR

┌─────────────────────────────────────────────────────────────┐
│                   Worktrees Only                            │
│                                                             │
│  ✅ Parallel development                                   │
│  ✅ Multiple working directories                           │
│  ✅ Isolated IDE state                                     │
│  ❌ Manual navigation (cd commands)                        │
│  ❌ Manual restacking (error-prone)                        │
│  ❌ No visual stack display                                │
└─────────────────────────────────────────────────────────────┘
```

### After: Get Both!

```
┌─────────────────────────────────────────────────────────────┐
│              Charcoal + Worktrees Integrated                │
│                                                             │
│  ✅ Parallel development                                   │
│  ✅ Easy navigation (worktree-aware)                       │
│  ✅ Automatic restacking (syncs worktrees)                 │
│  ✅ Visual stack display (with worktree info)              │
│  ✅ Multiple working directories                           │
│  ✅ Isolated IDE state                                     │
│  ✅ All Charcoal features work with worktrees!             │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Directory Structure

### Before (Charcoal Only)

```
my-repo/
├── .git/
│   └── .gt/              # Charcoal metadata
├── src/
├── tests/
└── ...

Single working directory
Can only work on one branch at a time
```

### After (Integrated)

```
my-repo/
├── .git/
│   ├── .gt/              # Charcoal metadata (shared!)
│   └── worktrees/        # Worktree metadata (shared!)
│
├── src/                  # Main repo (on main/master)
├── tests/
│
└── .trees/               # Worktrees directory
    ├── api/              # feature/api worktree
    │   ├── .git          # → points to main .git
    │   ├── src/
    │   └── ...
    │
    ├── ui/               # feature/ui worktree
    │   ├── .git          # → points to main .git
    │   ├── src/
    │   └── ...
    │
    └── polish/           # feature/polish worktree
        ├── .git          # → points to main .git
        ├── src/
        └── ...

Multiple working directories
Work on all branches simultaneously
All share Charcoal metadata!
```

## 🔄 Workflow Visualization

### Creating a Stack

```
Step 1: Create first branch with worktree
┌────────────────────────────────────────────────────────────┐
│ $ stack create feature/api main --worktree                 │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ main                                                        │
│  └── feature/api [WT: .trees/api]                         │
└────────────────────────────────────────────────────────────┘

Step 2: Create second branch stacked on first
┌────────────────────────────────────────────────────────────┐
│ $ stack create feature/ui feature/api --worktree           │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ main                                                        │
│  └── feature/api [WT: .trees/api]                         │
│       └── feature/ui [WT: .trees/ui]                      │
└────────────────────────────────────────────────────────────┘

Step 3: Create third branch stacked on second
┌────────────────────────────────────────────────────────────┐
│ $ stack create feature/polish feature/ui --worktree        │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ main                                                        │
│  └── feature/api [WT: .trees/api]                         │
│       └── feature/ui [WT: .trees/ui]                      │
│            └── feature/polish [WT: .trees/polish]         │
└────────────────────────────────────────────────────────────┘
```

### Parallel Development

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Development Setup                    │
└─────────────────────────────────────────────────────────────┘

Terminal 1              Terminal 2              Terminal 3
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ .trees/api/  │       │ .trees/ui/   │       │.trees/polish/│
│              │       │              │       │              │
│ Working on   │       │ Working on   │       │ Working on   │
│ API layer    │       │ UI layer     │       │ polish       │
│              │       │              │       │              │
│ feature/api  │       │ feature/ui   │       │feature/polish│
└──────────────┘       └──────────────┘       └──────────────┘
      ▲                      ▲                      ▲
      │                      │                      │
      └──────────────────────┴──────────────────────┘
                             │
                    All tracked by Charcoal!
                    Can navigate between them!
```

### Navigation Flow

```
Starting in .trees/polish/
┌────────────────────────────────────────────────────────────┐
│ $ pwd                                                       │
│ /path/to/repo/.trees/polish                                │
│                                                             │
│ $ eval $(stack up)    # Navigate to parent                 │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ Charcoal detects:                                          │
│ • Current branch: feature/polish                           │
│ • Parent branch: feature/ui                                │
│ • Parent has worktree at: .trees/ui                        │
│                                                             │
│ Output: cd /path/to/repo/.trees/ui                         │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ $ pwd                                                       │
│ /path/to/repo/.trees/ui                                    │
│                                                             │
│ $ eval $(stack up)    # Navigate to parent again           │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│ $ pwd                                                       │
│ /path/to/repo/.trees/api                                   │
└────────────────────────────────────────────────────────────┘
```

### Restacking Flow

```
Initial State:
┌────────────────────────────────────────────────────────────┐
│ main (commit A)                                             │
│  └── feature/api (commit B, based on A)                   │
│       └── feature/ui (commit C, based on B)               │
│            └── feature/polish (commit D, based on C)      │
└────────────────────────────────────────────────────────────┘

After feature/api is merged to main:
┌────────────────────────────────────────────────────────────┐
│ main (commit A + B)    ← feature/api merged!               │
│                                                             │
│ feature/ui (commit C, still based on old B) ← OUT OF DATE! │
│ feature/polish (commit D, based on C) ← OUT OF DATE!       │
└────────────────────────────────────────────────────────────┘

Run: stack restack
┌────────────────────────────────────────────────────────────┐
│ Step 1: Charcoal rebases feature/ui onto new main         │
│         feature/ui: B → C  becomes  main → C'              │
│                                                             │
│ Step 2: Charcoal rebases feature/polish onto new ui       │
│         feature/polish: C → D  becomes  C' → D'            │
│                                                             │
│ Step 3: Sync all worktrees                                 │
│         .trees/ui/ fetches and updates                     │
│         .trees/polish/ fetches and updates                 │
└────────────────────────────────────────────────────────────┘

Final State:
┌────────────────────────────────────────────────────────────┐
│ main (commit A + B)                                         │
│  └── feature/ui (commit C', rebased on new main)          │
│       └── feature/polish (commit D', rebased on new ui)   │
│                                                             │
│ All worktrees synced and up-to-date!                       │
└────────────────────────────────────────────────────────────┘
```

## 🎨 Command Visualization

### stack create

```
Input:  stack create feature/api main --worktree
        ─────────────────────────────────────────
        │         │            │         │
        │         │            │         └─ Create worktree
        │         │            └─────────── Base branch
        │         └──────────────────────── New branch name
        └────────────────────────────────── Command

Process:
┌─────────────────────────────────────────────────────────────┐
│ 1. git worktree add -b feature/api .trees/api main         │
│    ↓ Creates isolated directory                            │
│                                                             │
│ 2. Copy configs (.env, .vscode, .mcp.json, etc.)          │
│    ↓ Each worktree gets own settings                       │
│                                                             │
│ 3. gt branch track feature/api --parent main               │
│    ↓ Register in Charcoal                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Output:
┌─────────────────────────────────────────────────────────────┐
│ ✅ Created worktree: .trees/api                            │
│ 📂 Path: /path/to/repo/.trees/api                          │
│ 🌿 Branch: feature/api (Base: main)                        │
│ 🔗 Tracked in Charcoal                                     │
│                                                             │
│ To navigate:                                                │
│   cd .trees/api                                             │
└─────────────────────────────────────────────────────────────┘
```

### stack up

```
Input:  stack up
        ────────

Current Location: .trees/ui/ (feature/ui)

Process:
┌─────────────────────────────────────────────────────────────┐
│ 1. Detect current branch: feature/ui                       │
│    ↓                                                        │
│                                                             │
│ 2. Query Charcoal for parent: feature/api                  │
│    ↓                                                        │
│                                                             │
│ 3. Check if parent has worktree                            │
│    ↓ Yes! At .trees/api                                    │
│                                                             │
│ 4. Output cd command                                        │
└─────────────────────────────────────────────────────────────┘

Output:
┌─────────────────────────────────────────────────────────────┐
│ ℹ️  Navigating to worktree: .trees/api                     │
│ cd /path/to/repo/.trees/api                                 │
└─────────────────────────────────────────────────────────────┘

User runs: eval $(stack up)
New Location: .trees/api/ (feature/api)
```

### stack status

```
Input:  stack status
        ────────────

Process:
┌─────────────────────────────────────────────────────────────┐
│ 1. Get Charcoal stack: gt stack                            │
│    ↓                                                        │
│                                                             │
│ 2. For each branch, check for worktree                     │
│    ↓ git worktree list --porcelain                         │
│                                                             │
│ 3. Enhance output with worktree info                       │
└─────────────────────────────────────────────────────────────┘

Output:
┌─────────────────────────────────────────────────────────────┐
│ ╔════════════════════════════════════════════════════════╗ │
│ ║         STACK STATUS (with Worktrees)                  ║ │
│ ╚════════════════════════════════════════════════════════╝ │
│                                                             │
│ main                                                        │
│ ├── feature/api [WT: .trees/api] ← Has worktree!          │
│ │   └── feature/ui [WT: .trees/ui] ← Has worktree!       │
│ │       └── feature/polish [WT: .trees/polish] ← Has WT! │
│ └── hotfix/security ← No worktree                          │
└─────────────────────────────────────────────────────────────┘
```

### stack restack

```
Input:  stack restack
        ─────────────

Process:
┌─────────────────────────────────────────────────────────────┐
│ 1. Run gt restack in main repo                             │
│    ↓ Charcoal rebases all branches                         │
│                                                             │
│ 2. For each worktree:                                       │
│    ├─ cd .trees/api                                         │
│    │  git fetch origin feature/api                          │
│    │  Check if behind                                       │
│    │                                                         │
│    ├─ cd .trees/ui                                          │
│    │  git fetch origin feature/ui                           │
│    │  Check if behind                                       │
│    │                                                         │
│    └─ cd .trees/polish                                      │
│       git fetch origin feature/polish                       │
│       Check if behind                                       │
│                                                             │
│ 3. Sync metadata                                            │
└─────────────────────────────────────────────────────────────┘

Output:
┌─────────────────────────────────────────────────────────────┐
│ ℹ️  Using Charcoal to restack branches...                  │
│ ✅ Stack rebased successfully                              │
│ ℹ️  Syncing worktrees...                                   │
│ ℹ️  Syncing worktree: .trees/api (feature/api)            │
│ ℹ️  Syncing worktree: .trees/ui (feature/ui)              │
│ ℹ️  Syncing worktree: .trees/polish (feature/polish)      │
└─────────────────────────────────────────────────────────────┘
```

## 🔗 Metadata Connections

```
┌─────────────────────────────────────────────────────────────┐
│                    Shared Metadata                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ .git/.gt/    │  │ .git/        │                        │
│  │ (Charcoal)   │  │ worktrees/   │                        │
│  │              │  │ (Git)        │                        │
│  │ Stack info   │  │ Worktree     │                        │
│  │ Parent/child │  │ locations    │                        │
│  └──────┬───────┘  └──────┬───────┘                        │
│         │                 │                                │
│         └─────────────────┘                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    All Worktrees                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ .trees/api/  │  │ .trees/ui/   │  │.trees/polish/│    │
│  │              │  │              │  │              │    │
│  │ .git → main  │  │ .git → main  │  │ .git → main  │    │
│  │              │  │              │  │              │    │
│  │ All share    │  │ All share    │  │ All share    │    │
│  │ metadata!    │  │ metadata!    │  │ metadata!    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Key Benefits Visualized

```
┌─────────────────────────────────────────────────────────────┐
│                   Traditional Workflow                       │
│                                                             │
│  Time ──────────────────────────────────────────────────►  │
│                                                             │
│  API ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  UI  ░░░░░░░░████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  Polish ░░░░░░░░░░░░░░████████░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│                                                             │
│  ████ = Active work    ░░░░ = Waiting/blocked              │
│                                                             │
│  Total time: Long (sequential)                              │
│  Context switches: Many                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Integrated Workflow (Parallel)                  │
│                                                             │
│  Time ──────────────────────────────────────────────────►  │
│                                                             │
│  API ████████████████████████████████████████████████████  │
│  UI  ████████████████████████████████████████████████████  │
│  Polish ████████████████████████████████████████████████  │
│                                                             │
│  ████ = Active work (all parallel!)                        │
│                                                             │
│  Total time: Short (parallel)                               │
│  Context switches: None                                     │
└─────────────────────────────────────────────────────────────┘
```

---

**Ready to get started?**

```bash
stack init
stack create feature/my-feature main --worktree
cd .trees/my-feature
# Start coding in parallel! 🚀
```
