---
name: continuous-learning
description: >
  Guide Claude to extract session patterns into the instincts system.
  Use this whenever the evaluate-session hook fires or when a significant
  pattern is observed mid-session. Writes to ~/.claude/homunculus/instincts/personal/global.json.
version: 1.0
triggers:
  - evaluate-session hook fires (10+ message session)
  - significant pattern observed mid-session
  - session ending with learnable insights
---

# Continuous Learning Skill

This skill teaches Claude how to extract effective patterns from sessions into the persistent instincts system.

## When to Use

- **Auto-trigger:** When the evaluate-session hook fires at session end (message count ≥ 10)
- **Manual-trigger:** When you observe a pattern repeated 3+ times, receive a correction, or discover an effective workflow mid-session
- **Before compaction:** To preserve learned patterns before context loss

## Instinct Format

Instincts are stored as JSON in `~/.claude/homunculus/instincts/personal/global.json`:

```json
[
  {
    "id": "no-grep-for-symbols",
    "confidence": 0.85,
    "content": "When looking up Go symbols like function names or type names, always use Serena.findSymbol instead of Grep — Grep returns noisy line matches while Serena returns structured symbol metadata."
  },
  {
    "id": "parallel-independent-tools",
    "confidence": 0.92,
    "content": "When multiple tool calls are independent (no data dependencies), call them in parallel in a single message rather than sequentially. This saves tokens and reduces round-trips."
  }
]
```

**Fields:**
- `id`: Unique kebab-case identifier (e.g., "no-grep-for-symbols")
- `confidence`: Numeric score (0.0–1.0, see Scoring Rules below)
- `content`: Clear, actionable pattern statement (1–2 sentences)

## Confidence Scoring Rules

**Injection Threshold: 0.70**

Only instincts with confidence ≥ 0.70 are injected into future sessions. Writing below-threshold instincts wastes storage.

| Score | Criteria | Example |
|---|---|---|
| **0.90–1.00** | Pattern confirmed in multiple sessions; zero false positives | "Always use Serena.findSymbol for Go symbols — tested across 10 sessions" |
| **0.70–0.89** | Pattern observed clearly; may have edge cases | "Batch independent Serena calls — works for most queries, not multi-language ones" |
| **Below 0.70** | Don't write — insufficient evidence | "Might be faster to use Read first" — too vague, no data |

## When to Extract

Extract a pattern if:
1. **Repeated 3+ times** — Same technique used successfully in multiple contexts
2. **Correction given** — User or code feedback corrected an anti-pattern
3. **Effective workflow emerged** — New approach used consistently throughout session
4. **Tool preference validated** — Chose Tool A over Tool B and it clearly won

**Do NOT extract:**
- Hunches or single-occurrence techniques
- Style opinions (unless they affect performance/clarity)
- Incomplete or partially-working patterns

## Injection Mechanics

**Max 6 instincts per session** (highest confidence first)

When writing a new instinct:
- If ≥6 instincts already exist at ≥0.70 confidence, the lowest-confidence one is displaced
- Project-scoped instincts (`~/.serena/memories/`) override global ones
- Global instincts (`~/.claude/homunculus/instincts/personal/global.json`) are fallback

## Management Commands

**View current instincts with scores:**
```
/instinct-status
```
Lists all 6 injected instincts + their confidence scores + creation date

**Export instincts for sharing:**
```
/instinct-export
```
Outputs instincts as formatted markdown or JSON for documentation/sharing

**Analyze and improve structure:**
```
/evolve
```
Analyzes current instincts for overlap, conflicts, or missing patterns; suggests refinements

## Examples

### Example 1: Tool Priority Pattern
**Observation:** In 3 consecutive sessions, switching from Grep to Serena.findSymbol cut symbol lookup time by 40% and reduced context bloat.

**Instinct to write:**
```json
{
  "id": "serena-symbol-priority",
  "confidence": 0.88,
  "content": "Use Serena.findSymbol(symbol_name) for Go symbol lookup instead of Grep — returns structured metadata, not line text. 40% faster on large repos."
}
```

### Example 2: Batching Pattern
**Observation:** User repeatedly said "batch those calls" when I made sequential tool calls. Batched version consistently used less context.

**Instinct to write:**
```json
{
  "id": "batch-independent-tools",
  "confidence": 0.91,
  "content": "When 2+ tool calls have no dependencies, send them in parallel (one message) rather than sequentially. Saves tokens and reduces round-trips."
}
```

### Example 3: Anti-pattern Correction
**Observation:** User corrected a flawed assumption about hook behavior 3 times. Clear pattern.

**Instinct to write:**
```json
{
  "id": "hook-exit-codes",
  "confidence": 0.85,
  "content": "PreToolUse hooks: exit 0 to allow, exit 2 to block, exit nonzero to signal error. Never exit 1 on non-matching patterns — causes downstream failures."
}
```

## How to Write Instincts

1. **Identify the pattern** — What repeated technique or correction?
2. **Verify confidence** — Is it 0.70+? (multiple sessions or strong evidence)
3. **Write the id** — kebab-case, unique, descriptive
4. **Write the content** — 1–2 sentences, actionable, specific to Go/Claude/dotfiles context
5. **Append to global.json** — Use `Write` tool to append valid JSON array entry
6. **Validate JSON** — Ensure the file remains a valid JSON array

## Preventing Bad Instincts

Bad instincts displace good ones (max 6 per session). Avoid writing:
- **Vague:** "Might be useful to try batching sometimes"
- **Untested:** "I think Serena is faster" (no data)
- **One-off:** "That trick worked once" (need 3+ confirmations)
- **Contradictory:** "Both Tool A and Tool B are best" (pick one or explain context)

Low-confidence entries (< 0.70) waste the 6-instinct budget. Be selective.

## Post-Session Workflow

1. evaluate-session hook fires at session end (10+ messages)
2. [ContinuousLearning] signal appears in stderr
3. Review this skill to understand format and scoring rules
4. Identify 1–3 patterns from the session
5. Write high-confidence instincts to global.json
6. Next session: top 6 (by confidence) are auto-injected into session context

**File to update:** `~/.claude/homunculus/instincts/personal/global.json`

**Next session:** Verify instincts loaded via `/instinct-status` or in session context
