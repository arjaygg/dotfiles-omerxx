---
name: instinct-export
description: Export learned instincts, patterns, and conventions from the current session into structured YAML files for cross-session persistence.
---

# /instinct-export — Export Session Instincts

Export learned instincts and conventions from the current session as structured YAML entries for cross-session persistence.

## Usage

```
/instinct-export [--domain <name>] [--min-confidence <0-100>] [--output <file>] [--scope <project|global|all>]
```

## Flags

- `--domain <name>`: Export only instincts from the specified domain (e.g., `code-style`, `testing`, `architecture`)
- `--min-confidence <n>`: Minimum confidence threshold (0-100, default: 70)
- `--output <file>`: Output file path (prints to stdout when omitted)
- `--scope <project|global|all>`: Export scope (default: `all`)

## Output Format

Each instinct is exported as a YAML frontmatter block:

```yaml
---
confidence: 92
domain: code-style
source: session-observation
scope: project
project_id: a1b2c3d4e5f6
project_name: my-app
---
# Prefer Functional Style
## Action
Use functional patterns over classes.
```

## Behavior

1. Scan the current session for repeated corrections, confirmed patterns, and validated approaches
2. Filter by `--domain` and `--min-confidence` if specified
3. Format each instinct as a YAML block with metadata
4. Write to `--output` file or print to stdout
5. Report: N instincts exported, domains covered

## Integration

Exported instincts can be reviewed and committed to `.claude/rules/` for permanent enforcement.
