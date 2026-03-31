---
name: tmux-automation
description: Custom skills to leverage tmux commands, such as targeting specific panes, opening files in Neovim adjacent to the current pane, or spawning worktree dialogs.
triggers:
  - open in nvim
  - open adjacent
  - run in tmux pane
  - tmux popup
---

# Tmux Automation Skill

This skill provides the agent with the ability to interact with the user's tmux environment seamlessly.

## Capabilities

### 1. Open File in Adjacent Neovim Pane
**Use Case:** The user wants you to open a file they are discussing so they can edit it manually in their Neovim pane.
**Action:** Use the `Bash` tool to send keys to a specific tmux pane.
```bash
tmux send-keys -t right ":e <filename>" Enter
```
*(Adjust `-t right` based on the actual pane layout if known. You can use `tmux list-panes` to figure out the layout).*

### 2. Spawn Worktree Dialog
**Use Case:** The user wants to switch worktrees or create a new one using their custom popup dialog.
**Action:** Use the `Bash` tool to execute the user's custom script in a tmux popup:
```bash
tmux display-popup -E -w 80% -h 60% "$HOME/.dotfiles/tmux/scripts/claude-worktree-select.sh"
```

### 3. Send Command to a Specific Pane
**Use Case:** Sending a long-running process (like a dev server or subagent) to a dedicated pane.
**Action:** 
```bash
# Example: Send a build command to pane 2
tmux send-keys -t 2 "npm run build" Enter
```

### 4. Query Claude tmux State
**Use Case:** Check if Claude is active and what it's working on in the current tmux pane.
**Action:**
```bash
# Check Claude status in current pane
tmux display-message -p '#{@claude_status}'  # "working" or "idle"
tmux display-message -p '#{@claude_project}' # project name
tmux display-message -p '#{@claude_branch}'  # current branch
tmux display-message -p '#{@claude_worktree}' # worktree name (if in worktree)
```

### 5. Refresh Window Context
**Use Case:** Force refresh the tmux window name after a branch switch or context change.
**Action:**
```bash
~/.dotfiles/tmux/scripts/claude-tmux-bridge.sh session-start
```

## Instructions for Agent
1. When asked to "open" a file for the user, use the tmux `send-keys` command to open it in their Neovim session (assuming they have it open in an adjacent pane).
2. If interacting with subagents or background tasks, direct the output or command to a specific tmux pane so the user can monitor it.
3. The claude-tmux-bridge automatically manages window names and status. Use the bridge's `session-start` action to force a refresh if the window name gets out of sync.