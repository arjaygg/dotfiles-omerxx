# Skill: hyper-commit-setup

**Trigger:** User runs `/hyper-commit-setup` or says "set up hyper commit hooks", "install commit hooks", "enable atomic commits"

**Purpose:** Install hyper-atomic commit enforcement into the current git repo via `git config core.hooksPath`. Activates both git-level hooks (commit boundary) and confirms Claude Code IDE gates are active.

---

## Instructions

When this skill is invoked, follow these steps exactly:

### Step 1 — Verify we're in a git repo

```bash
git rev-parse --show-toplevel
```

If this fails, stop and tell the user: "This directory is not inside a git repository. Navigate to your project root and try again."

### Step 2 — Check if already installed

```bash
git config --local core.hooksPath
```

If the output is `~/.dotfiles/git/hooks` or expands to `$HOME/.dotfiles/git/hooks`:
- Report: "Hyper-atomic hooks are already installed in this repo."
- Run `~/.dotfiles/scripts/ai/atomic-status.sh` and show the current state.
- Stop here — do not reinstall.

### Step 3 — Ensure scripts are executable

```bash
chmod +x ~/.dotfiles/git/hooks/* ~/.dotfiles/scripts/ai/*
```

### Step 4 — Install hooks

```bash
git config core.hooksPath ~/.dotfiles/git/hooks
```

Confirm with:
```bash
git config --local core.hooksPath
```

### Step 5 — Offer to scaffold `.claude-atomic.yaml`

Ask the user:
> "Would you like to add a `.claude-atomic.yaml` to customize subsystem categories for this repo? (The default generic detection works for most projects.)"

If yes, scaffold a template:

```yaml
# .claude-atomic.yaml
# Customize subsystem detection for atomic-status.sh in this repo.
# Remove this file to use generic detection defaults.
subsystems:
  source: ["src/", "lib/", "app/"]
  tests: ["tests/", "test/", "spec/"]
  config: ["*.toml", "*.yaml", "*.json"]
  docs: ["docs/", "*.md"]
  infra: ["scripts/", ".github/", "Makefile", "Dockerfile"]
thresholds:
  max_files: 7
  max_subsystems: 3
  max_diff_lines: 300
```

Tell the user to edit the subsystem paths to match their project structure.

### Step 6 — Show current state

```bash
~/.dotfiles/scripts/ai/atomic-status.sh
```

### Step 7 — Print summary

Output a clean summary:

```
✅ Hyper-atomic commit hooks installed.

Git hooks active (core.hooksPath → ~/.dotfiles/git/hooks):
  • pre-commit:  protect-main, detect-private-key, check-large-files, check-atomicity
  • commit-msg:  enforce-commit-body (requires subject + body)

Claude Code gates active (pre-tool-gate.sh):
  • Blocks Edit/Write when state is 'blocked' (mixed concerns)
  • Blocks raw 'git commit' — use the canonical script instead

Canonical AI scripts:
  • ~/.dotfiles/scripts/ai/atomic-status.sh   → check current state
  • ~/.dotfiles/scripts/ai/commit.sh -m "subject" -m "why"  → validated commit
  • ~/.dotfiles/scripts/ai/checkpoint.sh "msg"  → WIP bounded checkpoint

Current state: <state from Step 6>

To remove: git config --unset core.hooksPath
```

---

## States Reference

| State | Meaning | Action |
|---|---|---|
| `in_progress` | Safe to continue editing | Keep going |
| `blocked` | Mixed concerns in staged files | Commit or split before editing more |
| `overgrown` | Too many files/lines staged | Checkpoint or split into smaller commits |
| `ready_to_commit` | (reserved for future use) | Commit now |

---

## Notes

- Hooks are stored at `~/.dotfiles/git/hooks/` (user-scoped, not stowed)
- `core.hooksPath` is set locally per repo (`.git/config`) — other repos are unaffected
- The Claude gate in `pre-tool-gate.sh` only activates in repos that have hooks installed
- To undo: `git config --unset core.hooksPath`
