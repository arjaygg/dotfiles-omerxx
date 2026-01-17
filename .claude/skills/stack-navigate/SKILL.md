---
name: stack-navigate
description: Navigate between stacked branches using Charcoal (gt up/down). Use when user wants to move to parent or child branch in their PR stack.
---

# Stack Navigate

Navigate between branches in a PR stack using Charcoal's `gt up` and `gt down` commands.

## When to Use

Use this skill when the user wants to:
- Move to the parent branch in their stack
- Move to a child branch in their stack
- Navigate up or down the stack hierarchy
- Switch between stacked branches without manual checkout

## Prerequisites

This skill requires **Charcoal CLI** to be installed and initialized:

```bash
# Install Charcoal
brew install danerwilliams/tap/charcoal

# Initialize in repository (if not already done)
./scripts/stack init
```

## Instructions

1. Parse the user's request to identify:
   - `direction`: "up" (to parent) or "down" (to child)
   - `child_index`: For "down", optional index if multiple children (default: 0)

2. Check if Charcoal is available and initialized:
   ```bash
   # Check if Charcoal is installed
   command -v gt &> /dev/null

   # Check if initialized in repo
   [ -d "$(git rev-parse --show-toplevel)/.gt" ]
   ```

3. Execute the navigation command:
   ```bash
   # Navigate up (to parent branch)
   ./scripts/stack up

   # Navigate down (to child branch)
   ./scripts/stack down

   # Navigate down to specific child (if multiple)
   ./scripts/stack down 1
   ```

4. If Charcoal is not available, inform the user:
   - Explain that navigation requires Charcoal
   - Provide installation instructions
   - Suggest manual checkout as alternative

5. Report the result:
   - Show the new current branch
   - Optionally show the stack status

## Fallback Behavior

If Charcoal is not installed or initialized, the script will:
1. Display an error message
2. Provide Charcoal installation instructions
3. Suggest manual branch checkout as alternative

## Examples

### Navigate Up

User: "Go to the parent branch"
Action:
```bash
./scripts/stack up
```

User: "Move up in the stack"
Action:
```bash
./scripts/stack up
```

### Navigate Down

User: "Go to the child branch"
Action:
```bash
./scripts/stack down
```

User: "Move to the second child branch"
Action:
```bash
./scripts/stack down 1
```

### Check Stack First

User: "Where am I in the stack?"
Action:
```bash
./scripts/stack status
# Then navigate based on user's request
```

## Related Skills

- **stack-create**: Create new stacked branches
- **stack-status**: View the stack hierarchy
- **stack-update**: Update stack after merge (includes restack option)

## Troubleshooting

### "Charcoal not initialized"

Run:
```bash
./scripts/stack init
```

### "Already at the top of the stack"

The current branch has no parent in the stack (it targets main directly).

### "No children to navigate to"

The current branch has no child branches stacked on top of it.
