# Style Lens

Derived from `code-health`'s complexity/duplication analysis. Runs on code changes by default (see
`lenses.toml`).

## What to check

- **Cyclomatic complexity**: functions at or above CCN≥15 ("Brain Method") or CCN≥10 ("Complex
  Method") — count decision points (if/for/while/case/&&/||) per function.
- **Function length**: functions at or above ~70 LOC ("Large Method") — a strong proxy for doing
  too many things in one place.
- **Cognitive complexity**: deep nesting (nested conditionals/loops) that makes a function hard to
  hold in your head even when its cyclomatic count is moderate.
- **Duplication (DRY violations)**: near-identical logic blocks repeated across the change or
  against existing code, that should be extracted into a shared function.
- **Hotspots**: when git history is available, files with both high churn and complexity
  violations are priority refactor targets — call these out specifically, they compound over time.

## Process

1. Measure or estimate complexity/length/nesting for functions touched by the change. Exact
   tooling (e.g. a CCN calculator) is optional — a careful manual count is acceptable when tooling
   isn't wired up.
2. For duplication, confirm the blocks are genuinely equivalent (same behavior, not just visually
   similar) before flagging — coincidental similarity isn't a DRY violation.
3. Emit one finding per confirmed issue: `lens: "style"`, `location`, `trigger_condition` (e.g.
   "CCN 18, exceeds Brain Method threshold"), `guard_snippet` (the concrete refactor — extract
   method, flatten nesting, dedupe into a shared helper), `potential_consequence` (maintenance cost:
   harder to modify safely, higher bug rate in high-churn files). No `severity` field.
4. This lens is about maintainability, not correctness — do not duplicate findings the
   `correctness` lens already owns (a complex function with a genuine logic bug gets a
   `correctness` finding for the bug and, separately, a `style` finding for the complexity if both
   are true).
