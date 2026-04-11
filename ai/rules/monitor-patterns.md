# Monitor Patterns

Claude Code's `Monitor` tool runs a shell command whose stdout is the event stream.
Each stdout line → one notification in your session. Silent → zero tokens charged.

## When to Use Monitor vs Alternatives

| Intent | Use |
|--------|-----|
| "Tell me every time X happens" (continuous) | `Monitor` (`persistent: true`) |
| "Run this and tell me when done" (one-shot) | `Bash(run_in_background: true)` |
| "Do X every N minutes regardless" (time-driven) | `/loop` or `CronCreate` |
| "Watch for events AND act on them in-session" | `Monitor` in main session |
| "Complex multi-step reaction to events" | `Monitor` → spawn `Agent` on event |

**Key decision:** Is the goal "tell me when C changes" or "do X on a schedule"?
- Changes/events → Monitor
- Scheduled work → loop/cron

## Core Rules

1. **Always use `grep --line-buffered`** in pipes — without it, pipe buffering delays events by minutes
2. **Never pipe raw output** — every stdout line becomes a chat message; filter aggressively
3. **Handle API errors with `|| true`** — one failed request must not kill the monitor
4. **Remote APIs: 30s+ intervals** — rate limits apply (GitHub, k8s API, cloud CLIs)
5. **Local files/processes: 0.5–1s** — fine-grained polling is fine locally
6. **Only stdout triggers events** — stderr goes to the output file but is silent in chat

## Pattern 1 — GitHub Actions Status Stream

Emits one line per completed run only when status changes (not on every poll):

```bash
REPO="owner/repo"
LAST=""
while true; do
  NOW=$(gh run list --repo "$REPO" --limit 5 \
    --json databaseId,status,conclusion,headBranch \
    --jq '.[] | "\(.databaseId)|\(.status)|\(.conclusion)|\(.headBranch)"' \
    2>/dev/null || echo "")
  if [ "$NOW" != "$LAST" ] && [ -n "$NOW" ]; then
    diff <(echo "$LAST") <(echo "$NOW") 2>/dev/null \
      | grep "^>" | sed 's/^> //' \
      | grep --line-buffered "completed" || true
    LAST="$NOW"
  fi
  sleep 30
done
```

Config: `persistent: true`, `description: "GitHub Actions on owner/repo"`

## Pattern 2 — Kubernetes Pod Watch

```bash
kubectl get pods -n NAMESPACE -w \
  | grep --line-buffered -E "(Failed|Error|CrashLoopBackOff|OOMKilled|Pending)"
```

Config: `persistent: true`, `description: "pod failures in NAMESPACE"`

For log streaming from a specific pod:
```bash
kubectl logs -f -n NAMESPACE deploy/APP_NAME 2>/dev/null \
  | grep --line-buffered -E "(ERROR|FATAL|panic|exception)"
```

## Pattern 3 — Log File Tail

```bash
tail -f /path/to/app.log | grep --line-buffered -E "(ERROR|FATAL|panic)"
```

Config: `persistent: true` for session-length watching, or `timeout_ms: 1800000` (30 min) for bounded tasks.

## Pattern 4 — ArgoCD App Health

Emits only when app is NOT healthy+synced:

```bash
while true; do
  STATUS=$(argocd app get APP_NAME --output json 2>/dev/null \
    | jq -r '"\(.metadata.name)|\(.status.health.status)|\(.status.sync.status)"' \
    || echo "APP_NAME|Unknown|Unknown")
  echo "$STATUS"
  sleep 30
done | grep --line-buffered -vE "Healthy\|Synced"
```

Config: `persistent: true`, `description: "ArgoCD health for APP_NAME"`

## Pattern 5 — DB Migration Progress

Stream migration runner logs for progress + error lines:

```bash
kubectl logs -f -n NAMESPACE deploy/MIGRATION_RUNNER 2>/dev/null \
  | grep --line-buffered -E "(migrating|applied|failed|error|rows processed|complete)"
```

Config: `timeout_ms: 3600000` (1 hr), `description: "DB migration progress"`

## Pattern 6 — Poll-and-Diff (Generic "emit on change")

Reusable template for any resource that should emit only when state changes:

```bash
LAST=""
while true; do
  NOW=$(YOUR_CHECK_COMMAND 2>/dev/null || echo "")
  if [ "$NOW" != "$LAST" ]; then
    echo "CHANGED: $NOW"
    LAST="$NOW"
  fi
  sleep INTERVAL_SECONDS
done
```

Variants:
- PR review state: replace `YOUR_CHECK_COMMAND` with `gh pr view NUM --json reviewDecision --jq '.reviewDecision'`
- Deploy status: replace with `kubectl rollout status deploy/APP -n NS 2>&1 | tail -1`
- Health endpoint: replace with `curl -s https://api/health | jq -r '.status'`

## Common Mistakes

| Mistake | Impact | Fix |
|---------|--------|-----|
| `cmd \| grep "ERROR"` | Events delayed minutes by pipe buffer | `cmd \| grep --line-buffered "ERROR"` |
| Piping `gh run list` raw | 100+ lines per poll → auto-stopped | Filter with `--jq` before stdout |
| No error handling on API calls | One timeout kills the entire monitor | Add `2>/dev/null \|\| echo ""` |
| Using Monitor for one-shot tasks | Unnecessary persistent watch | Use `Bash(run_in_background: true)` |
| 5–10s intervals on GitHub/cloud APIs | Rate limit errors | Use 30s minimum for remote APIs |
| stderr without redirect | Errors are invisible in notifications | Add `2>&1` when stderr matters |

## Reacting to Monitor Events

When Monitor fires a notification:
1. **Parse** the event line (structured format helps: `KEY=value KEY2=value2`)
2. **Classify** the event (severity, type, context)
3. **Route** by classification:
   - Simple → inline action in main session
   - Complex multi-step → `Agent(subagent_type, ...)` for remediation
4. **Acknowledge** by recording acted IDs to avoid double-processing

Keep reaction logic in the main session. Only spawn agents when the response is multi-step or requires specialized context (e.g., `cicd-auto-retry`, `cicd-review`).
