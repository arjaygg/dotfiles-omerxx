---
name: tmux-orchestrator
description: Orchestrate multiple agent CLI sessions (Claude Code, Cursor, Codex, AGY) persistently using Tmux for the Orchestrator-Worker paradigm.
---

# Tmux Orchestrator Skill

This skill provides instructions for the Coordinator agent to orchestrate worker agents across different CLI environments (such as Claude Code, Cursor, Codex, and AGY) using persistent Tmux sessions.

## Core Concepts

By using Tmux, you can spawn persistent "Sidekick" sessions that retain context and are highly token-efficient compared to spinning up ephemeral agents that must re-read all context on each turn.

### Spawning Worker Sessions
To spawn a new, persistent terminal pane for a worker agent:
```bash
# Split the current window horizontally and start the desired CLI agent
tmux split-window -h "<agent_cli>"
```
*(Replace `<agent_cli>` with `claude`, `codex`, `agy`, or the appropriate Cursor CLI command).*

### Programmatic Input Injection
To send a prompt or follow-up instruction to a specific persistent terminal window (e.g., targeting pane index `1`):
```bash
tmux send-keys -t 1 "<prompt>" Enter
```

### Scraping Output
To read what is happening in the sub-agent’s window and feed it back to your orchestrator logic:
```bash
tmux capture-pane -p -t 1
```

### Programmatic Completion Signaling
To pause the orchestrator and wait for a worker to finish, instruct the worker to output a recognizable message (e.g., "WORKER_COMPLETED"). Then, use Tmux synchronization:
```bash
tmux wait-for -s "WORKER_COMPLETED"
```

### Peeking and Self-Healing
CLI agents often get stuck on interactive prompts (e.g., "Do you want to run this command?"). You must implement a "peeking" mechanism:
1. Periodically capture the pane to check the output.
2. If the worker is stalled on a confirmation prompt, programmatically inject an `Enter` or `y` to unblock it:
```bash
tmux send-keys -t 1 "y" Enter
```

## Guidelines for Use
1. Always generate a per-worker frozen spec (`plans/specs/<label>.md`, template: `plans/specs/TEMPLATE.md`) before spawning a worker to provide unambiguous instructions. Never use a single shared `plans/spec.md`.
2. Instruct the worker to refer to its `plans/specs/<label>.md` as its primary input.
3. Check worker pane status regularly to apply self-healing if needed.
4. Send a termination command to the worker once its tasks are fully completed and verified.
