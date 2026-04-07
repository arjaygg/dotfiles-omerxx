50 lines → 35 unique
last 15 unique lines:
- proposed action
### Step 3: Generate Rule Files
For each approved rule, create a file at `.claude/hookify.{name}.local.md`:
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
[lean-ctx: 266→122 tok, -54%]
