---
name: hookify
description: Convert observed AI behavior (repeated corrections, patterns, anti-patterns) into persistent hook rules stored in .claude/hookify.*.local.md files.
---

# /hookify — Behavior → Hook Rule

Convert an observed behavior or correction into a persistent hook rule so you don't need to repeat the instruction.

## Usage

```
/hookify <observed-behavior>
```

## Behavior

### Step 1: Understand the Pattern
Identify the observed behavior, correction, or anti-pattern. Extract:
- What triggered it (event: bash, file write, stop, prompt, all)
- What should happen (action: block, warn)
- How to detect it (pattern: regex)

### Step 2: Propose the Rule
Show the proposed rule to the user before creating it:
```
Rule name: <name>
Event: <bash|file|stop|prompt|all>
Action: <block|warn>
Pattern: <regex>
Message: <shown when rule triggers>
```
Ask for approval before writing.

### Step 3: Generate Rule Files
For each approved rule, create a file at `.claude/hookify.<name>.local.md`:
```yaml
---
name: rule-name
enabled: true
event: bash|file|stop|prompt|all
action: block|warn
pattern: "regex pattern"
---
Message shown when rule triggers.
```

### Step 4: Confirm
Report created rules and how to manage them with `/hookify-list` and `/hookify-configure`.

## Examples

```
/hookify I keep using cd instead of absolute paths
→ Creates rule: warn on any Bash command starting with "cd "

/hookify always use gh auth switch before gh pr in dotfiles repo
→ Creates rule: warn on gh pr/issue/repo commands without auth switch check
```
