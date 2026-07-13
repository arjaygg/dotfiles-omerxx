---
name: evolve
description: Analyze instincts and suggest reviewable evolution candidates
command: true
---

# Evolve Command

## Implementation

This repository does not ship an `instinct-cli.py` implementation. Treat `/evolve` as
review guidance, not as permission to execute a guessed plugin path or mutate canonical
policy. Use the `continuous-learning` skill to inspect the documented instinct format,
then validate any proposed policy artifact with the repository-side validator:

```bash
python3 scripts/policy_proposal.py validate path/to/proposal.json
```

For a deterministic baseline-vs-candidate review report, provide numeric metric artifacts:

```bash
python3 scripts/policy_proposal.py review path/to/proposal.json \
  --baseline path/to/baseline.json \
  --candidate path/to/candidate.json
```

The report is always `review-required`; it never promotes or applies the proposal.

After a human review, record an accept, reject, or defer decision in an explicitly chosen
JSONL ledger. The ledger stores a proposal hash and rationale, not raw evidence:

```bash
python3 scripts/policy_decision.py path/to/proposal.json \
  --ledger /path/outside-the-repository/decisions.jsonl \
  --decision reject \
  --rationale "Insufficient recurrence" \
  --decided-at 2026-07-13
```

Recording a decision never applies or promotes the proposal.

An external evolution implementation may be used only when its installed path and
output directory are explicitly verified. Generated artifacts remain candidates and
must stay outside canonical policy until human review.

Analyzes instincts and clusters related ones into higher-level structures:
- **Commands**: When instincts describe user-invoked actions
- **Skills**: When instincts describe auto-triggered behaviors
- **Agents**: When instincts describe complex, multi-step processes

## Usage

```
/evolve                    # Analyze all instincts and suggest evolutions
```

## Evolution Rules

### → Command (User-Invoked)
When instincts describe actions a user would explicitly request:
- Multiple instincts about "when user asks to..."
- Instincts with triggers like "when creating a new X"
- Instincts that follow a repeatable sequence

Example:
- `new-table-step1`: "when adding a database table, create migration"
- `new-table-step2`: "when adding a database table, update schema"
- `new-table-step3`: "when adding a database table, regenerate types"

→ Creates: **new-table** command

### → Skill (Auto-Triggered)
When instincts describe behaviors that should happen automatically:
- Pattern-matching triggers
- Error handling responses
- Code style enforcement

Example:
- `prefer-functional`: "when writing functions, prefer functional style"
- `use-immutable`: "when modifying state, use immutable patterns"
- `avoid-classes`: "when designing modules, avoid class-based design"

→ Creates: `functional-patterns` skill

### → Agent (Needs Depth/Isolation)
When instincts describe complex, multi-step processes that benefit from isolation:
- Debugging workflows
- Refactoring sequences
- Research tasks

Example:
- `debug-step1`: "when debugging, first check logs"
- `debug-step2`: "when debugging, isolate the failing component"
- `debug-step3`: "when debugging, create minimal reproduction"
- `debug-step4`: "when debugging, verify fix with test"

→ Creates: **debugger** agent

## What to Do

1. Detect current project context
2. Read project + global instincts (project takes precedence on ID conflicts)
3. Group instincts by trigger/domain patterns
4. Identify:
   - Skill candidates (trigger clusters with 2+ instincts)
   - Command candidates (high-confidence workflow instincts)
   - Agent candidates (larger, high-confidence clusters)
5. Show promotion candidates (project -> global) when applicable
6. If a reviewer explicitly requests candidate generation, write only to an ignored,
   explicitly selected staging directory outside canonical policy; do not infer a home
   path or write directly into `AGENTS.md`, `CLAUDE.md`, rules, skills, hooks, or CI.

Generated artifacts are candidates only. They must be represented by a validated,
evidence-backed proposal before review; `/evolve` must not edit canonical policy,
change enforcement levels, or promote/merge its own output. Validate a proposal with:

```bash
python3 scripts/policy_proposal.py validate path/to/proposal.yaml
```

## Output Format

```
============================================================
  EVOLVE ANALYSIS - 12 instincts
  Project: my-app (a1b2c3d4e5f6)
  Project-scoped: 8 | Global: 4
============================================================

High confidence instincts (>=80%): 5

## SKILL CANDIDATES
1. Cluster: "adding tests"
   Instincts: 3
   Avg confidence: 82%
   Domains: testing
   Scopes: project

## COMMAND CANDIDATES (2)
  /adding-tests
    From: test-first-workflow [project]
    Confidence: 84%

## AGENT CANDIDATES (1)
  adding-tests-agent
    Covers 3 instincts
    Avg confidence: 82%
```

## Flags

No repository-side execution flags are provided. External plugin flags must not be
assumed to exist; verify the installed implementation before using them.

## Generated File Format

### Command
```markdown
---
name: new-table
description: Create a new database table with migration, schema update, and type generation
command: /new-table
evolved_from:
  - new-table-migration
  - update-schema
  - regenerate-types
---

# New Table Command

[Generated content based on clustered instincts]

## Steps
1. ...
2. ...
```

### Skill
```markdown
---
name: functional-patterns
description: Enforce functional programming patterns
evolved_from:
  - prefer-functional
  - use-immutable
  - avoid-classes
---

# Functional Patterns Skill

[Generated content based on clustered instincts]
```

### Agent
```markdown
---
name: debugger
description: Systematic debugging agent
model: sonnet
evolved_from:
  - debug-check-logs
  - debug-isolate
  - debug-reproduce
---

# Debugger Agent

[Generated content based on clustered instincts]
```
