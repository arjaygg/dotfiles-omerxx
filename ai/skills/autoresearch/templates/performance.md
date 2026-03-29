# Performance Optimization Template

Pre-filled configuration for reducing latency, response time, or increasing throughput.

## Fields

```
Goal: Reduce {metric_name} to below {target}
Scope: {hot path files — controllers, services, repositories}
Metric: {p95 latency ms | avg response time ms | throughput req/s}
Direction: lower (for latency/time) or higher (for throughput)
Verify: {benchmark command — see examples below}
Guard: {test suite — no regressions}
Iterations: 10
Role: Dev
```

## Verify Command Examples

| Scenario | Verify Command |
|---|---|
| HTTP endpoint latency | `for i in $(seq 1 10); do curl -s -o /dev/null -w "%{time_total}" http://localhost:5000/api/endpoint; done \| awk '{sum+=$1} END {printf "%.0f", sum/NR*1000}'` |
| Go benchmark | `go test -bench=BenchmarkTarget -benchtime=5s ./pkg/... 2>&1 \| grep BenchmarkTarget \| awk '{print $3}' \| tr -d 'ns/op'` |
| Database query | `time psql -c "EXPLAIN ANALYZE SELECT ..." 2>&1 \| grep "Execution Time" \| awk '{print $3}'` |

## Strategy Notes

- Profile before optimizing — measure, don't guess
- Focus on algorithmic improvements (O(n) → O(1)) over micro-optimizations
- Watch for: N+1 queries, unnecessary allocations, blocking I/O, missing indices
- Each change should be independently measurable — don't batch optimizations
- The guard prevents "fast but broken" — a faster endpoint that returns wrong data is worse
