# Test Fix Template

Pre-filled configuration for driving failing test count to zero.

## Fields

```
Goal: Make all tests pass (zero failures)
Scope: {auto-detect from project — source files, not test files}
Metric: Failing test count
Direction: lower
Verify: {auto-detect by language}
Guard: {build compiles}
Iterations: 10
Role: Dev
```

## Auto-Detection by Language

| Language | Verify Command | Guard Command |
|---|---|---|
| Go | `go test ./... 2>&1 \| grep -c "^--- FAIL" \|\| echo 0` | `go build ./...` |
| C# | `dotnet test --no-build 2>&1 \| grep -oP 'Failed:\s+\K\d+' \|\| echo 0` | `dotnet build --no-restore` |
| TypeScript | `npx jest 2>&1 \| grep -oP 'Tests:\s+\K\d+ failed' \| grep -oP '\d+' \|\| echo 0` | `npx tsc --noEmit` |

## Strategy Notes

- Fix one test per iteration, prioritizing by impact: build errors > type errors > test failures > lint
- Read the error message carefully — most failures have obvious causes
- Never delete, skip, or suppress a test to reduce the count
- Never add `@ts-ignore`, `any` types, or `//nolint` directives
- If a test depends on external state (DB, API), check test fixtures first
