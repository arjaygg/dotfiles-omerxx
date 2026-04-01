# Progress: Stack Skills Overhaul

**Branch:** `chore/stack-skills-overhaul`  
**Plan:** `plans/proud-tinkering-rose.md`

## In Progress

## Done
- [x] Created branch `chore/stack-skills-overhaul`

## Backlog

### Wave 1 (foreground — prerequisite)
- [x] T14 — Create `lib/gh-account.sh` + migrate `create-pr.sh` to use it

### Wave 2 (parallel background — after T14)
- [ ] T1 — Fix `create-stack.sh` base branch default (current branch, not main)
- [ ] T3 — Rewrite `merge-stack.sh` GitHub-only + use `gh-account.sh`

### Wave 3 (parallel background)
- [x] T4 — Add PR base update loop to `update-stack.sh` + use `gh-account.sh`
- [ ] T8 — Fix `stack-auto-pr-merge` Python Task() → Agent tool syntax

### Wave 4 (parallel background — skill files only)
- [ ] T5 — Fix tmux window-exists check in `stack-navigate` + `stack-create`
- [ ] T6 — Add post-merge tmux window cleanup to `stack-merge` skill
- [ ] T7 — Add tmux bridge refresh call to `stack-create` skill

### Wave 5 (parallel background — new files)
- [ ] T10 — New `stack-clean` skill + script
- [ ] T11 — New `stack pr-all` script + skill + entrypoint routing

### Wave 6 (skill polish)
- [ ] T2 — Fix `stack-pr` skill `gt log awk NR==2` → delegate to script
- [ ] T9 — Add stack chain visualization to PR body in `create-pr.sh`
- [ ] T12 — Add optional draft PR prompt to `stack-create` skill
- [ ] T13 — Rename `sync-base` → `stack-sync` + `gt sync` + update `setup.sh`

## Blocked
