# Git Worktree + Tmux + Claude Workflow

Complete workflow for managing multiple parallel development contexts with git worktrees, tmux, and Claude Code.

## Overview

- **Subagent**: Creates and manages git worktrees (in `.trees/` directory)
- **Tmux Script**: Opens Claude in worktree panes
- **Keybinding**: `<prefix> w` to quickly open worktree in new pane

## Complete Workflow

### Scenario: Work on urgent bug while keeping main work

```
┌────────────────────────────────────────────────────────────┐
│ Terminal (tmux session)                                    │
├────────────────────────────────────────────────────────────┤
│ Pane 1: Main work (~/auc-conversion)                      │
│ $ claude                                                    │
│                                                             │
│ You: "Create a worktree for TIME transformer precision bug"│
│                                                             │
│ Claude (via git-worktree-tmux subagent):                  │
│   ✅ Created worktree: .trees/time-precision-fix          │
│   📂 Path: ~/auc-conversion/.trees/time-precision-fix     │
│   🌿 Branch: feature/time-precision-fix                    │
│                                                             │
│   Would you like me to open this in a new tmux pane?      │
│   (yes/no)                                                  │
│                                                             │
│ You: "yes"                                                  │
│                                                             │
│ [Subagent runs tmux script, new pane appears]             │
├────────────────────────────────────────────────────────────┤
│ Pane 1: Main work          │ Pane 2: TIME fix worktree    │
│ (validation feature)        │ (.trees/time-precision-fix)  │
│                             │                               │
│ You: Continue main work    │ You: "Fix TIME(7) precision  │
│                             │       in transformer"         │
│                             │                               │
│                             │ Claude: [implements fix]      │
└────────────────────────────────────────────────────────────┘
```

## Quick Commands

### Create Worktree (via Claude subagent)

```
You: "Create worktree for [feature-name]"

Claude:
  - Creates .trees/feature-name
  - Sets up branch feature/feature-name
  - Copies .env, .vscode/, .claude/
  - Offers to open in new tmux pane
```

### Open Existing Worktree in New Pane

**Keybinding**: `<prefix> w` (where prefix = Ctrl+A)

This will:
1. Show fzf picker with existing worktrees
2. Select one
3. Open new tmux pane in that worktree
4. Start Claude automatically

**Manual**:
```bash
~/.dotfiles/tmux/scripts/claude-worktree.sh [worktree-name]
```

### List All Worktrees

```
You: "List my worktrees"

Claude:
  - Shows all active worktrees
  - Shows which have Claude sessions running
  - Shows current worktree (if in one)
```

### Remove Worktree

```
You: "Remove worktree [feature-name]"

Claude:
  - Checks for uncommitted changes
  - Verifies not currently in use
  - Removes worktree and branch
```

## Keybindings Reference

### Your Existing Tmux Keys
- `Ctrl+A` - Prefix
- `Ctrl+A o` - sessionx (session manager)
- `Ctrl+A p` - floax (floating window)

### New Worktree Key
- `Ctrl+A w` - Open worktree in new pane (fzf picker)

## Tmux Navigation Between Worktrees

Once you have multiple panes:

```bash
# Switch between panes
Ctrl+A → arrow keys    # Move focus to adjacent pane
Ctrl+A q [number]      # Jump to pane by number

# Zoom pane (full screen)
Ctrl+A z               # Toggle zoom on current pane

# Close pane (exit Claude session first)
Ctrl+A x               # Kill current pane

# Resize panes
Ctrl+A Ctrl+arrow      # Resize in direction
Ctrl+A Alt+arrow       # Resize in larger increments
```

## Typical Daily Workflow

### Morning: Start Main Work

```bash
cd ~/auc-conversion
tmux new -s auc-work
claude

# Work on main feature in this pane
```

### Urgent Bug Arrives

```
You (in Claude): "Create worktree for hotfix-date-conversion"

Claude: Creates .trees/hotfix-date-conversion
        Opens in new pane automatically

# New pane appears on the right
# You're now in the worktree with fresh Claude session
```

### Switch Back to Main Work

```bash
# Just switch panes with Ctrl+A → left arrow
# Your main work context is preserved
```

### Multiple Parallel Features

```bash
# Pane layout:
┌─────────────┬─────────────┬─────────────┐
│ Main work   │ Hotfix      │ Refactor    │
│ (main)      │ (worktree1) │ (worktree2) │
└─────────────┴─────────────┴─────────────┘

# Use Ctrl+A w to add more worktree panes
# Or manually: Ctrl+A % (split vertical)
```

### End of Day: Clean Up

```
You: "List my worktrees"
Claude: Shows 3 active worktrees

# For each completed one:
You: "Remove worktree hotfix-date-conversion"
Claude: Removes it safely

# Or manually close panes:
Ctrl+A x (in each pane)
```

## Tips & Tricks

### Keep Main Work in Leftmost Pane

Establish pattern: Main work always in pane 0 (left)
Worktrees in panes 1, 2, 3... (right side)

### Use Tmux Zoom for Focus

Working on worktree? Zoom it:
```bash
Ctrl+A z    # Toggle full screen for current pane
```

### Quick Status Check

```
You: "Show status of all worktrees"

Claude: For each worktree:
  - Branch name
  - Uncommitted changes
  - Last commit
  - Active Claude session?
```

### Reattach to Existing Worktrees

If you close tmux but worktrees exist:

```bash
# Restart tmux session
tmux attach -t auc-work

# Open existing worktrees with keybinding
Ctrl+A w
# Select from fzf picker
```

## Directory Structure

```
auc-conversion/
├── .trees/                    # All worktrees here
│   ├── time-precision-fix/
│   ├── validation-refactor/
│   └── hotfix-alf-date/
├── .gitignore                 # Contains .trees/
└── [main repo files]

Each worktree has:
  - .env (copied from main)
  - .vscode/ (copied from main)
  - .claude/ (copied from main)
  - Independent working directory
  - Own feature branch
```

## Troubleshooting

### Worktree exists but not showing in fzf

```bash
ls -la .trees/    # Verify worktree exists
git worktree list # Check git knows about it
```

### Can't open new pane (keybinding doesn't work)

```bash
# Reload tmux config
tmux source-file ~/.dotfiles/tmux/tmux.conf

# Or restart tmux session
```

### Subagent not creating worktrees

Check subagent is loaded:
```bash
ls -la ~/.dotfiles/.claude/agents/
# Should see git-worktree-tmux.md
```

### Claude session in worktree using wrong directory

Exit and restart:
```bash
# In the pane
/exit

# Then reopen with script
~/.dotfiles/tmux/scripts/claude-worktree.sh [name]
```

## Advanced: Custom Layouts

Save your preferred layout:

```bash
# Create 3-pane layout (main + 2 worktrees)
tmux split-window -h
tmux split-window -h
tmux select-layout even-horizontal

# Save layout
tmux display-message "#{window_layout}"
# Copy the output, add to alias
```

Add to your shell aliases:
```bash
alias auc-layout='tmux select-layout "..."'
```

## Integration with Other Tools

### With sessionx (your existing plugin)

```bash
Ctrl+A o    # Open sessionx
# Shows all sessions
# Each worktree can be its own session if desired
```

### With floax (your existing plugin)

```bash
Ctrl+A p    # Open floating terminal
# Use for quick commands without affecting pane layout
```

## Summary

**Key Innovation**: Subagent creates worktrees + Tmux automatically opens them in new panes

**Workflow**:
1. Work in main pane (Claude session)
2. Ask Claude to create worktree (subagent)
3. Claude offers to open in new pane (tmux script)
4. New pane appears with Claude already in worktree
5. Switch between panes as needed (Ctrl+A + arrows)
6. Close panes when done (Ctrl+A x)
7. Ask Claude to clean up worktrees (subagent)

**Result**: Seamless parallel development without manual cd/terminal management
