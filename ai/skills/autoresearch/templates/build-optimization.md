# Build Optimization Template

Pre-filled configuration for reducing build or compilation time.

## Fields

```
Goal: Reduce build time to below {target} seconds
Scope: {build configs, project files, Dockerfiles, CI configs}
Metric: Build duration in seconds
Direction: lower
Verify: {timed build command — see examples below}
Guard: {build output works — run smoke test}
Iterations: 10
Role: Dev
```

## Verify Command Examples

| Build System | Verify Command |
|---|---|
| .NET | `{ time dotnet build --no-restore 2>&1; } 2>&1 \| grep real \| awk '{print $2}' \| sed 's/m/*60+/;s/s//' \| bc` |
| Go | `{ time go build ./... 2>&1; } 2>&1 \| grep real \| awk '{print $2}' \| sed 's/m/*60+/;s/s//' \| bc` |
| Docker | `{ time docker build -t test . 2>&1; } 2>&1 \| grep real \| awk '{print $2}' \| sed 's/m/*60+/;s/s//' \| bc` |
| npm/TypeScript | `{ time npm run build 2>&1; } 2>&1 \| grep real \| awk '{print $2}' \| sed 's/m/*60+/;s/s//' \| bc` |

## Strategy Notes

- Parallelize independent build steps where possible
- Remove unused project references and NuGet/npm packages
- Enable incremental/tiered compilation flags
- Docker: multi-stage builds, layer caching, optimize .dockerignore
- CI: cache dependencies, use build matrices for parallel jobs
- Don't change target frameworks or major dependencies — too risky for a build-speed loop
