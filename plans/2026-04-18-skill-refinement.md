# Skill Refinement & Development Plan — 2026-04-18

## Objective
Refine 5 existing skills (/cap, /fury, /stark, /strange, /vision) and create a new /dev skill following a unified best-practice template based on /hawk. All skills must adhere to:
- **Tool Priority Rules**: Serena, pctx batching, qmd for docs, MemPalace for memory
- **Engineering Principles**: Lean-Agile, Evolutionary Architecture, Test-First, TDD, BDD
- **Guidance Documents**: Golang Unit Testing Guide, AI Agent Testing Best Practices

## Refinement Checklist

### Phase 1: Baseline & Analysis
- [ ] Review /hawk skill structure (template reference)
- [ ] Extract key patterns from /hawk design
- [ ] Document refinement strategy

### Phase 2: Skill Refinement
- [ ] Refine /cap (Orchestrator) — tool alignment, batching, memory access
- [ ] Refine /fury (Test-Driven Development) — TDD focus, tool priority
- [ ] Refine /stark (Architect & Planner) — planning phase, Serena usage
- [ ] Refine /strange (Debugging Agent) — systematic approach, tool chains
- [ ] Refine /vision (DevOps CI/CD) — pipeline analysis, tool batching

### Phase 3: New Skill Creation
- [ ] Create /dev skill (golang dev + general dev, using /skill-creator)
- [ ] Ensure /dev follows same patterns as refined skills

### Phase 4: Advisor Review
- [ ] Run advisor review on all refinements
- [ ] Capture final refinements from advisor feedback
- [ ] Finalize outputs

---

## Hawk Template Analysis

### Key Patterns to Adopt
1. **Clear Trigger Section** — multiple trigger phrases
2. **Allowed Tools** — explicit list with Serena tools included
3. **Dynamic Context Injection** — injects git/env context
4. **Step-by-Step Instructions** — numbered phases with explicit decisions
5. **Tool Priority Compliance**:
   - Uses Serena for memory and symbol navigation
   - Batches context reads (`Promise.all` pattern)
   - Uses Serena for knowledge access (not direct file reads)
6. **Multi-Agent Coordination** — registers as leader, spawns subagents
7. **Specific Output Format** — structured findings with severity ranking

---

## Refinement Strategy

Each skill needs:
1. **Frontmatter Audit** — ensure all tools are declared
2. **Tool Chain Review** — replace Bash/Grep with Serena equivalents
3. **Batching Opportunities** — identify sequential ops that can be parallel
4. **Memory Integration** — replace knowledge fetching with MemPalace/Serena
5. **Guidance Alignment** — embed references to Golang Testing Guide, TDD practices
6. **Output Format** — ensure structured, actionable results

---

## Development Status
- Created: 2026-04-18
- Status: In Planning
