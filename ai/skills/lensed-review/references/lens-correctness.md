# Correctness Lens

Baseline lens for any review. Derived from `hawk`'s Architecture and Quality dimensions and
`pr-review`'s Tests dimension.

## What to check

- **Architecture**: does the change fit the existing module boundaries, or does it introduce a
  layering violation (e.g. a UI component reaching directly into a data-access layer)?
- **Logic correctness**: off-by-one errors, incorrect conditionals, mishandled edge cases (empty
  input, nil/null, zero, max values), incorrect assumptions about ordering or concurrency.
- **Quality**: dead code, unreachable branches, obviously duplicated logic that should be a shared
  function (report via the `style` lens instead if it's purely a duplication concern, not a
  correctness one).
- **Tests**: does the change have test coverage proportional to its risk? Flag missing tests for
  new branches or edge cases, not missing tests in general — this is not a coverage-percentage
  lens.

## Process

1. Read the diff or target file(s) in full before forming any opinion — do not comment on a
   snippet out of context.
2. For each candidate issue, confirm it against the actual code path (trace the call, don't guess
   from the name of a function).
3. Emit one finding per confirmed issue in the shared finding contract (see
   `ai/skills/cap/references/schemas.md`): `lens: "correctness"`, `location`, `trigger_condition`,
   `guard_snippet`, `potential_consequence`. Do not emit a `severity` field.
4. Do not report stylistic-only concerns here — route those to the `style` lens instead.

## Language auto-detection (from `hawk`)

Detect project language from root files before applying language-specific correctness checks:
- `go.mod` → Go
- `pyproject.toml` → Python
- `tsconfig.json` → TypeScript

Apply language-idiomatic correctness checks (e.g. Go: unchecked errors, goroutine leaks; Python:
mutable default arguments, bare `except`; TypeScript: `any` masking a real type error).
