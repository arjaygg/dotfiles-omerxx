# Coverage Optimization Template

Pre-filled configuration for increasing test coverage to a target percentage.

## Fields

```
Goal: Increase test coverage to {target, default: 90}%
Scope: {auto-detect from project}
Metric: Line coverage percentage
Direction: higher
Verify: {auto-detect by language}
Guard: {build must compile}
Iterations: 10
Role: QA
```

## Auto-Detection by Language

| Language | Scope Pattern | Verify Command | Guard Command |
|---|---|---|---|
| Go | `**/*_test.go` | `go test -coverprofile=coverage.out ./... && go tool cover -func=coverage.out \| tail -1 \| awk '{print $NF}' \| tr -d '%'` | `go build ./...` |
| C# | `**/*Tests.cs` | `dotnet test --collect:"XPlat Code Coverage" --results-directory ./coverage && find ./coverage -name "coverage.cobertura.xml" -exec grep -oP 'line-rate="\K[^"]+' {} \; \| awk '{printf "%.1f", $1*100}'` | `dotnet build --no-restore` |
| TypeScript | `**/*.test.ts, **/*.spec.ts` | `npx jest --coverage 2>&1 \| grep "All files" \| awk '{print $10}' \| tr -d '%'` | `npx tsc --noEmit` |

## Strategy Notes

- Start with uncovered files that have the most public methods — highest coverage gain per iteration
- Prefer testing real behavior over trivial getter/setter tests
- Each test should assert meaningful outcomes, not just line execution
- If coverage plateaus, look for untested error paths and edge cases
