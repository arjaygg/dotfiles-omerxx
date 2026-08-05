# Mutation Testing Gate Template

Pre-filled configuration for Tech Lead quality gate — validating that tests are meaningful
via mutation testing and coverage thresholds.

## Fields

```
Goal: Achieve mutation kill rate ≥ {target, default: 80}% and coverage ≥ {coverage_target, default: 80}%
Scope: {source files under test — NOT test files}
Metric: Mutation kill rate percentage
Direction: higher
Verify: {mutation testing command — see examples below}
Guard: {all existing tests pass}
Iterations: 10
Role: TL
```

## Verify Command Examples

| Language | Tool | Verify Command |
|---|---|---|
| Go | gremlins | `gremlins unleash --tags "!integration" ./pkg/... 2>&1 \| grep "Kill rate" \| awk '{print $NF}' \| tr -d '%'` |
| Go | go-mutesting | `go-mutesting ./pkg/... 2>&1 \| tail -1 \| awk '{print $NF}' \| tr -d '%'` |
| C# | Stryker | `dotnet stryker 2>&1 \| grep "Mutation score" \| awk '{print $NF}' \| tr -d '%'` |
| TypeScript | StrykerJS | `npx stryker run 2>&1 \| grep "Mutation score" \| awk '{print $NF}' \| tr -d '%'` |

## Strategy Notes

- Mutation testing validates test quality, not just coverage — a test that covers a line
  but doesn't assert anything useful will have surviving mutants
- Low kill rate on a file means tests are passing but not actually checking behavior
- Focus iterations on files with the most surviving mutants — highest improvement potential
- The TL role does NOT modify source code — it improves tests to catch more mutations
- Scope should be source files (what gets mutated), but the TL modifies test files
- Guard ensures existing tests still pass after test improvements
