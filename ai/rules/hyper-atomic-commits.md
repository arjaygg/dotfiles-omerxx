# Hyper-Atomic Commit Strategy

These rules enforce hyper-atomic commit discipline for AI coding agents. They apply in any git repo where `core.hooksPath` is set to `~/.dotfiles/git/hooks`.

> **Precedence:** When active, these rules supersede `global-developer-guidelines.md` for commit operations (stricter: wrapper scripts required instead of raw git).

## Activation Check

Before applying these rules, verify hooks are installed:

```bash
git config --local core.hooksPath
```

If the output is NOT `~/.dotfiles/git/hooks`, these rules do not apply — the repo has not opted in.

## Canonical Scripts

**Always use these instead of raw git commands:**

| Task | Script | Raw command (BLOCKED) |
|---|---|---|
| Check state | `~/.dotfiles/scripts/ai/atomic-status.sh` | — |
| Commit | `~/.dotfiles/scripts/ai/commit.sh -m "type(scope): subject" -m "why"` | `git commit` |
| Checkpoint (WIP) | `~/.dotfiles/scripts/ai/checkpoint.sh "message"` | `git commit --no-verify` |

**Never use raw `git commit`** in a hyper-atomic repo. The canonical `commit.sh` validates conventional commit format, enforces a meaningful body explaining the "why," and tracks intent for drift detection.

## Atomic States

Run `~/.dotfiles/scripts/ai/atomic-status.sh` to get the current state. There are four possible states:

- **`in_progress`** — Safe to continue editing. No staged changes or staged changes are within thresholds.
- **`blocked`** — Mixed concerns detected across staged files (too many subsystems). **Stop editing. Commit or split before changing more files.**
- **`overgrown`** — Too many files or diff lines staged. Consider committing a focused subset before continuing.
- **`ready_to_commit`** — Changes are staged and within thresholds. Commit now before editing more files.

## Thresholds (defaults, overridable via `.claude-atomic.yaml`)

- **max_files:** 7 staged files
- **max_subsystems:** 3 distinct subsystem categories
- **max_diff_lines:** 300 added+removed lines

## When to Check State

Run `atomic-status.sh`:
1. **Before committing** — to confirm the commit will pass the pre-commit hook.
2. **After staging 5+ files** — to catch overgrowth early.
3. **When a `git commit` fails** — the pre-commit hook rejected it; check state to understand why.
4. **Before starting a new logical change** — if prior work is staged but uncommitted.

## Recovery Actions by State

- **`blocked`**: Unstage files that don't belong to the current concern (`git reset HEAD <file>`), then commit the focused subset. Or use `checkpoint.sh` to save WIP and start clean.
- **`overgrown`**: Commit a smaller subset of related files, or use `checkpoint.sh` if the work is incomplete but verified.
- **`ready_to_commit`**: Run `commit.sh` with a conventional commit message and meaningful body.

## Commit Message Format

All commits must follow conventional commit format with a body:

```
type(scope): concise subject line

Body explaining WHY this change is needed.
The body must be at least 10 meaningful characters.
```

Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`

## Per-Repo Customization

Place a `.claude-atomic.yaml` at the repo root to customize subsystem detection and thresholds:

```yaml
subsystems:
  source: ["src/", "lib/"]
  tests: ["tests/", "spec/"]
  config: ["*.toml", "*.yaml"]
thresholds:
  max_files: 10
  max_subsystems: 4
  max_diff_lines: 500
```

## Setup

To install hyper-atomic hooks in a new repo:
```bash
git config core.hooksPath ~/.dotfiles/git/hooks
```

To verify installation:
```bash
~/.dotfiles/scripts/ai/atomic-status.sh --verbose
```
