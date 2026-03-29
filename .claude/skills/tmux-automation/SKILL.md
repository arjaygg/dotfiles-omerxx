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

## Instructions for Agent
1. When asked to "open" a file for the user, use the tmux `send-keys` command to open it in their Neovim session (assuming they have it open in an adjacent pane).
2. If interacting with subagents or background tasks, direct the output or command to a specific tmux pane so the user can monitor it.