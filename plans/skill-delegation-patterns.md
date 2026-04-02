# Skill Delegation Patterns — Analysis from Session f3ca7a1f

**Date:** 2026-04-03  
**Session analyzed:** `/Users/axos-agallentes/git/auc-conversion/.trees/k8s-supervisor-platform` (325 tool calls, 0 Serena/MCP)

---

## Root Cause: Skills Were Never Invoked

Session data showed:
- **40 Grep calls** that should have routed to `explore` skill → `Serena.findSymbol()`
- **80 Read calls** (some whole-file) → some should have routed to `explore` → `Serena.getSymbolsOverview()`
- **3 subagents spawned** (Haiku x2, Opus x1) that used Bash/Read but NOT `pctx-code-mode` skill
- **0 MCP tool calls** → no Serena used at all

**Why:** The model never recognized that it should invoke a skill. It went straight to native tools.

---

## Pattern 1: Recognition Failure (Skills Never Triggered)

**The violation:**
```
Model output: "Let me search for WorkerPool using Grep"
Should have been: "Let me search for WorkerPool using the explore skill"
```

**Recognition signals that were missed:**
- "find where", "search for", "where is" → should trigger `explore` skill
- "explain this", "understand how", "describe" → should trigger `gemini` skill
- "write tests", "generate mock", "refactor" → should trigger `codex` skill

**Why recognition failed:**
1. Skills are in CLAUDE.md as **behavioral guidance**, not enforcement
2. No hook intercepts "Let me grep" → "Use explore skill instead"
3. Skills require explicit invocation (user says "explore" or model decides to call it)
4. Model has no penalty for skipping skills; native tools work fine

---

## Pattern 2: Multi-Model Routing (Wrong Tool Choice)

**From CLAUDE.md global rules:**
```
Auto-invoke `gemini` skill when:
  - Explain/summarize/describe a file, function, module
  - Understand how something works
  - Answer broad codebase Q&A
  
Auto-invoke `codex` skill when:
  - Write unit or integration tests
  - Generate boilerplate
  - Rename a symbol (mechanical refactor)
```

**Session reality:**
- Subagent A (Haiku) was **explaining worker registration state machine**
  - Should have triggered `gemini` skill
  - Instead used Read + Bash (inefficient)
- Subagent B (Haiku) was **investigating E2E test failure**
  - Should have triggered `explore` skill (finding relevant code)
  - Instead used Glob + Read + Bash
- Subagent C (Opus) was **running cluster diagnostics**
  - Correctly used Bash (kubectl, monitoring tools)
  - No skill routing issue here

**Pattern rule:**
```
Task type              → Should route to      → Why
=====================================================
Explain/summarize      → gemini skill        → Better model, explain is not coding
Explore/find/search    → explore skill       → Serena is structurally aware
Write tests            → codex skill         → Pattern-following, boilerplate
Refactor/rename        → codex skill         → Mechanical, token-efficient
Debug/diagnose         → Keep in main        → Requires access to logs, CLI
Business logic         → Keep in main        → Reasoning + implementation
```

---

## Pattern 3: Skill Invocation Timing

**Too early (skip the skill check):**
```
User: "Fix the login bug"
Model: "I'll grep for the error, then fix it"
❌ Should have done: explore → find → understand → then fix
```

**Too late (skills not mentioned):**
```
Model decides to explore without skill
→ Uses native Grep
→ Gets context flooded
→ Compaction happens earlier
→ Lost context mid-task
```

**Right time (skill-first):**
```
User: "Fix the login bug"
Model: "Let me explore where login is handled"
→ Invokes explore skill
→ explore calls Serena.findSymbol("LoginHandler")
→ Returns structured result
→ Then model examines and fixes
```

---

## Pattern 4: Skill vs Agent (Orthogonal)

Confusion point: **Skills and agents are different axes.**

```
                Invoke Skill?
                 YES    NO
  Use Agent?  +------+------+
       YES    | A    | B    |
             +------+------+
       NO     | C    | D    |
             +------+------+

A: Skill + Agent (rare)
   E.g., /explore (skill) → spawns Explore agent
   
B: Agent without Skill (common, but suboptimal)
   E.g., spawn general-purpose agent, it uses Grep instead of exploring
   
C: Skill without Agent (ideal for small tasks)
   E.g., /explore (skill) → runs Serena directly, returns results
   
D: Neither Skill nor Agent (worst)
   E.g., Model uses native tools directly (like session f3ca7a1f)
```

**Session f3ca7a1f was Quadrant D:**
- No skills invoked
- Agents spawned (B instead of C/A)
- Result: inefficient tool use, context flood

---

## Pattern 5: When Skills Should Auto-Invoke

Skills have **trigger phrases** defined in their SKILL.md. The model should recognize these:

**explore skill triggers:**
- "explore", "find symbol", "where is", "how does", "search for", "look for", "what calls", "show me the code", "understand", "navigate to", "find usages"

**Session reality:**
- Subagent output: "I need to understand the worker registration state machine"
  - Trigger phrase: "understand" ✅
  - Skill invoked: ❌ (should have been `gemini`)
  
- Model: "Let me search for WorkerPool"
  - Trigger phrase: "search for" ✅
  - Skill invoked: ❌ (should have been `explore`)

**Why triggers weren't recognized:**
- Skills are optional guidance, not enforced
- No hook validates trigger phrases
- Model is free to choose native tools

---

## Pattern 6: Cost of Skill Avoidance

**Session f3ca7a1f metrics:**
| Metric | Value |
|--------|-------|
| Total tool calls | 325 |
| Grep calls (should be Serena) | 40 |
| Read calls (some should be Serena) | 80 |
| MCP/Serena calls | 0 |
| Context waste estimate | 40-80 tokens per Grep call |
| **Total wasted tokens** | **1,600–3,200 tokens** |

With skills:
- 40 Grep → 40 × Serena.findSymbol() = 40 structured results (not lines)
- 80 Read → some → Serena.getSymbolsOverview() = 80 × lower line count
- **Token savings: 30-50%** over the session

---

## Pattern 7: Skill Selection Decision Tree

```
START: "What task is this?"
  |
  +-- "Find/explore/search/where is"?
  |    → invoke explore skill (Serena-first exploration)
  |
  +-- "Explain/understand/describe/summarize"?
  |    → invoke gemini skill (better at reasoning)
  |
  +-- "Write tests/generate/mock/boilerplate"?
  |    → invoke codex skill (pattern-following)
  |
  +-- "Rename across codebase/mechanical refactor"?
  |    → invoke codex skill (token-efficient)
  |
  +-- "Debug/diagnose/run commands/logs"?
  |    → stay in main model (needs CLI access)
  |
  +-- "Implement feature/business logic"?
  |    → stay in main model (reasoning + coding)
  |
  +-- "Explain/discuss policies/best practices"?
  |    → invoke ollama skill (if offline/cost-sensitive)
  |
  → (default) stay in main model
```

---

## Implementation: Auto-Invoke Skills via Hook

**Proposal:** Add `UserPromptSubmit` hook to detect skill triggers and inject reminder.

```bash
# ~/.dotfiles/.claude/hooks/skill-trigger-reminder.sh

PROMPT=$(cat)

# Check for explore triggers
if echo "$PROMPT" | grep -iE "(find|explore|search|where is|show me|understand|navigate)" >/dev/null; then
  echo "💡 SKILL HINT: This looks like an exploration task."
  echo "   Consider invoking /explore skill → Serena will search structurally."
  exit 0
fi

# Check for gemini triggers  
if echo "$PROMPT" | grep -iE "(explain|understand|describe|summarize|how does)" >/dev/null; then
  echo "💡 SKILL HINT: This looks like an explanation task."
  echo "   Consider invoking /gemini skill → specialized reasoning model."
  exit 0
fi

# Check for codex triggers
if echo "$PROMPT" | grep -iE "(write test|generate|mock|boilerplate|refactor|rename)" >/dev/null; then
  echo "💡 SKILL HINT: This looks like a coding task."
  echo "   Consider invoking /codex skill → specialized coding model."
  exit 0
fi

exit 0
```

---

## Summary Table

| Situation | Action | Outcome |
|-----------|--------|---------|
| **Model uses Grep for symbol lookup** | Should have invoked `/explore` | 40 tokens wasted instead of 1 |
| **Model reads entire file without limit** | Should have invoked `/explore` → `getSymbolsOverview` | 80 tokens wasted instead of 5 |
| **Subagent explains state machine** | Should have invoked `/gemini` | Haiku used as reasoner (suboptimal) |
| **Model generates test boilerplate** | Should have invoked `/codex` | Lost pattern library, manual generation |
| **Model debugs via CLI** | Correctly stayed in main | ✅ Right choice |

---

## Key Insight

**Skills are not a coding problem — they're a decision-making problem.**

The model can execute with or without skills. Skills are "better" in specific domains (explore = structure search, gemini = reasoning, codex = pattern generation), but nothing *forces* the choice.

**Current state:** Skills are optional guidance.  
**Needed:** Skills need enforcement or strong nudging (hooks that remind, not block).

Session f3ca7a1f would have saved 30-50% token budget **just by invoking explore skill** for the 40 Grep calls.

