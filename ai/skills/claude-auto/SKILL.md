---
name: claude-auto
description: >
  Autonomous PR pipeline orchestrator. Triggered by GitHub issues labeled 'claude-auto'.
  Runs 6 phases: setup → implement+test-loop → parallel-review → PR+CI → cleanup → issue-comment.
  Language-agnostic. Invokable as a skill for local dry-runs or from CI via headless claude.
triggers:
  - /claude-auto
  - run claude-auto
  - autonomous pr
  - auto-implement issue
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskGet
  - advisor
---

# claude-auto — Autonomous PR Pipeline Orchestrator

Implements a GitHub issue end-to-end: branch → implement → test-loop → 3-agent review →
PR → CI wait → bugbot fix → admin-merge → cleanup → issue comment.

## Persistence Directive

This skill does **not stop midway**. Once invoked it runs to completion or posts a failure
comment on the issue and exits with a clear reason. Use `TodoWrite` to track phase progress.

---

## Invocation Modes

| Mode | How |
|------|-----|
| **CI (primary)** | GitHub Actions calls `claude -p` with this skill prompt |
| **Local dry-run** | `/claude-auto <issue-number>` in a Claude Code session |
| **Background agent** | `Agent(subagent_type: "general-purpose", prompt: <this skill>)` |

---

## Required Environment

| Variable | Source | Purpose |
|----------|--------|---------|
| `GH_TOKEN` | `ADMIN_GITHUB_TOKEN` secret | Push, PR create, admin merge, issue comment |
| `ANTHROPIC_API_KEY` | `CLAUDE_API_KEY` secret | Headless claude for reviewer sub-agents |
| `ISSUE_NUMBER` | Workflow input | Issue to implement |
| `DIFF_SIZE_MAX` | Workflow input (default 500) | Soft self-check before opening PR |
| `MAX_TEST_ITERATIONS` | Workflow input (default 5) | Test-fix loop cap |

---

## Phase 0 — TodoWrite Checklist

Before doing any work:

```
TodoWrite([
  { id: "setup",       content: "Phase 1: Create branch, read issue",             status: "pending" },
  { id: "implement",   content: "Phase 2: Implement change + test loop",           status: "pending" },
  { id: "review",      content: "Phase 3: 3-agent parallel review + apply fixes",  status: "pending" },
  { id: "diff-check",  content: "Phase 4: Diff size self-check",                   status: "pending" },
  { id: "pr",          content: "Phase 5: Commit, push, create PR",                status: "pending" },
  { id: "ci",          content: "Phase 6: Wait for CI, fix bugbot",                status: "pending" },
  { id: "merge",       content: "Phase 7: Admin merge",                            status: "pending" },
  { id: "cleanup",     content: "Phase 8: Delete branch",                          status: "pending" },
  { id: "comment",     content: "Phase 9: Post summary, close issue",              status: "pending" },
])
```

---

## Phase 1 — Setup

Mark `setup` in_progress.

```bash
# Fetch issue details
ISSUE_JSON=$(gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/issues/$ISSUE_NUMBER)
ISSUE_TITLE=$(echo "$ISSUE_JSON" | jq -r '.title')
ISSUE_BODY=$(echo "$ISSUE_JSON"  | jq -r '.body // ""')
LABELS=$(echo "$ISSUE_JSON" | jq -r '[.labels[].name] | join(",")')

# Branch name
SLUG=$(echo "$ISSUE_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/-\+/-/g' | sed 's/^-\|-$//g' | cut -c1-40)
BRANCH="feat/claude-auto-${ISSUE_NUMBER}-${SLUG}"

# Create branch
git checkout -b "$BRANCH" main
```

Read the issue body carefully. Identify:
1. What change is requested
2. Which files are likely affected
3. Acceptance criteria (if stated)
4. Any constraints (language, framework, patterns to follow)

Mark `setup` completed.

---

## Phase 2 — Implement + Test Loop

Mark `implement` in_progress.

### 2a — Implement

Using Serena or Read/Edit tools, implement the minimum change that satisfies the issue.
Follow the project's existing patterns — read nearby files before writing new code.

### 2b — Test loop (max `$MAX_TEST_ITERATIONS` iterations)

Detect and run the test suite:

```bash
detect_test_runner() {
  if [ -f go.mod ];                             then echo "go test ./..."; return; fi
  if [ -f package.json ];                       then echo "npm test"; return; fi
  if [ -f pyproject.toml ] || [ -f setup.py ];  then echo "python -m pytest"; return; fi
  if [ -f Gemfile ];                            then echo "bundle exec rspec"; return; fi
  if grep -q "^test:" Makefile 2>/dev/null;     then echo "make test"; return; fi
  echo ""
}
TEST_CMD=$(detect_test_runner)
```

Loop:
1. Run `$TEST_CMD`; capture stdout + stderr
2. If exit 0: all green — break
3. If exit non-zero:
   - Parse failure output to identify failing test(s) and root cause
   - Fix the specific failures — do not touch passing tests
   - Increment iteration counter
4. After `$MAX_TEST_ITERATIONS` failures: post failure comment on the issue and exit 1

```
ABORT MESSAGE (post to issue if test loop exhausted):
## claude-auto: test loop exhausted

Could not get all tests green after $MAX_TEST_ITERATIONS iterations.

**Last failure:**
```
<last test output here>
```

**What was tried:**
<summary of fix attempts>

Please review and either fix the issue description or implement manually.
```

Mark `implement` completed.

---

## Phase 3 — Parallel Review

Mark `review` in_progress.

Get the list of changed files:
```bash
CHANGED_FILES=$(git diff main...HEAD --name-only | tr '\n' ' ')
```

Spawn 3 agents **simultaneously** using 3 parallel `Agent` tool calls.
Each agent receives the changed file list and its specific focus area.

### Security Agent

```
You are a security code reviewer. Review these changed files for security vulnerabilities.

Changed files: <CHANGED_FILES>

Read each file and check for:
1. OWASP Top 10 violations:
   - Injection (SQL, command, LDAP, XPath)
   - Broken authentication (weak session mgmt, missing rate limiting)
   - Sensitive data exposure (PII, secrets, tokens in logs/responses)
   - XML External Entities (XXE)
   - Broken access control (missing authz checks)
   - Security misconfiguration (debug on, default creds, open CORS)
   - Cross-Site Scripting (XSS) — if frontend code
   - Insecure deserialization
   - Known vulnerable dependency versions
   - Insufficient logging of security events
2. Hardcoded secrets, API keys, passwords, connection strings
3. Missing input validation at system boundaries (user input, external APIs)
4. Missing authorization checks on new endpoints or functions

Return a JSON array of findings:
[{"severity":"critical|high|medium|low","category":"security","file":"path","line":42,"description":"...","fix":"...","confidence":0.9}]

Return an empty array [] if no issues found. Return ONLY the JSON array.
```

### Performance Agent

```
You are a performance code reviewer. Review these changed files for performance issues.

Changed files: <CHANGED_FILES>

Read each file and check for:
1. N+1 database queries (loop containing a query or ORM call)
2. Missing indexes for new query patterns (check schema/migration files)
3. Unbounded loops or O(n²) algorithms where n could be large at runtime
4. Missing caching on hot read paths (frequently called, rarely changing data)
5. Memory leaks: unclosed file handles, connections, or growing unbounded slices/maps
6. Blocking calls in async or concurrent contexts (sync I/O in async fn, blocking in goroutine)
7. Unnecessary re-computation inside loops (hoist invariants out)

Return a JSON array of findings:
[{"severity":"critical|high|medium|low","category":"performance","file":"path","line":42,"description":"...","fix":"...","confidence":0.9}]

Return an empty array [] if no issues found. Return ONLY the JSON array.
```

### Style Agent

```
You are a style and maintainability code reviewer. Review these changed files.

Changed files: <CHANGED_FILES>

Read each file and check for:
1. Naming: unclear variable/function names, non-idiomatic casing for the language
2. Missing or stale documentation on exported/public symbols
3. Functions longer than 40 lines (candidates to extract)
4. Duplicated logic (3+ identical/near-identical blocks — extract helper)
5. Magic numbers or strings that should be named constants
6. Non-idiomatic patterns: reinventing stdlib utilities, verbose where concise is idiomatic
7. Inconsistency with neighboring code style (check 2-3 adjacent files)

Return a JSON array of findings:
[{"severity":"critical|high|medium|low","category":"style","file":"path","line":42,"description":"...","fix":"...","confidence":0.9}]

Return an empty array [] if no issues found. Return ONLY the JSON array.
```

### Apply findings

After all 3 agents complete, collect findings arrays and:

1. **CRITICAL + HIGH** → apply fixes immediately using Edit/Write tools
2. **MEDIUM + LOW** → collect for PR description
3. Re-run tests after applying fixes (one final pass — no iteration limit here; revert if new failures introduced)

Store a summary string:
```
REVIEW_SUMMARY="Security: X critical/high fixed, Y medium/low logged
Performance: X critical/high fixed, Y medium/low logged
Style: X critical/high fixed, Y medium/low logged"
```

Mark `review` completed.

---

## Phase 4 — Diff size self-check

Mark `diff-check` in_progress.

```bash
CHANGED_LINES=$(git diff main...HEAD --stat | tail -1 | awk '{print $1}')
LABEL_APPROVED=$(gh pr view "$BRANCH" --json labels --jq '[.labels[].name] | contains(["large-diff-ok"])' 2>/dev/null || echo "false")

if [ "${CHANGED_LINES:-0}" -gt "${DIFF_SIZE_MAX:-500}" ] && [ "$LABEL_APPROVED" != "true" ]; then
  gh issue comment "$ISSUE_NUMBER" --body "## claude-auto: diff too large

The implementation produces a diff of **$CHANGED_LINES lines** (max $DIFF_SIZE_MAX).

Add the \`large-diff-ok\` label to issue #$ISSUE_NUMBER to override, or narrow the scope."
  exit 1
fi
```

Note: The `claude-auto-diff-size-gate` required check in GitHub Actions provides the hard
backstop regardless of this self-check.

Mark `diff-check` completed.

---

## Phase 5 — Commit, push, create PR

Mark `pr` in_progress.

```bash
git add -A
git commit -m "feat: $ISSUE_TITLE

Closes #$ISSUE_NUMBER

Co-authored-by: claude-auto[bot] <claude-auto[bot]@users.noreply.github.com>"

git push origin "$BRANCH"
```

Build PR body (include MEDIUM/LOW review findings):
```bash
PR_BODY="## Summary
Automated implementation of #${ISSUE_NUMBER}: ${ISSUE_TITLE}.

## Changes
<describe what changed and why, 3-5 bullets>

## Review findings addressed
${REVIEW_SUMMARY}

### MEDIUM/LOW findings (logged, not auto-fixed)
<list any medium/low findings for human review>

## Test results
All tests passing after N iteration(s).

Closes #${ISSUE_NUMBER}"

PR_URL=$(gh pr create \
  --title "feat: $ISSUE_TITLE" \
  --body "$PR_BODY" \
  --base main \
  --head "$BRANCH")
PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')
```

Mark `pr` completed.

---

## Phase 6 — Wait for CI and fix Bugbot

Mark `ci` in_progress.

Poll for up to 20 minutes (20 × 60s):

```bash
CI_GREEN=false
for i in $(seq 1 20); do
  echo "CI poll $i/20..."
  
  # Check for failing (non-gate) checks
  FAILING=$(gh pr checks "$PR_NUMBER" \
    --json name,state \
    --jq '[.[] | select(.state != "SUCCESS" and .state != "SKIPPED" and .name != "claude-auto-coverage-gate" and .name != "claude-auto-diff-size-gate")] | length' \
    2>/dev/null || echo "1")
  
  if [ "$FAILING" = "0" ]; then
    CI_GREEN=true
    break
  fi
  
  # Look for new Bugbot / bot review comments and fix them
  BUGBOT_COMMENTS=$(gh pr view "$PR_NUMBER" --json reviews \
    --jq '.reviews[] | select(.author.login | test("bot|bugbot|github-actions|dependabot"; "i")) | .body' \
    2>/dev/null || echo "")
  
  if [ -n "$BUGBOT_COMMENTS" ]; then
    # Feed bot findings to Claude for remediation
    # (The orchestrator reads these and applies targeted fixes)
    BUGBOT_FINDINGS="$BUGBOT_COMMENTS"
  fi
  
  sleep 60
done
```

If Bugbot findings were captured: read them, apply targeted fixes, push a new commit,
then resume the poll loop (reset i back to 1 after each push to give CI time to re-run).
Limit bugbot fix rounds to 3 to prevent infinite loops.

If `CI_GREEN` is still false after polling: post failure comment on issue and exit 1.

Mark `ci` completed.

---

## Phase 7 — Admin merge

Mark `merge` in_progress.

```bash
gh pr merge "$PR_NUMBER" --squash --admin \
  --subject "feat: $ISSUE_TITLE (#$PR_NUMBER)"
```

If merge fails: post failure comment with PR URL and exit 1.

Mark `merge` completed.

---

## Phase 8 — Cleanup

Mark `cleanup` in_progress.

```bash
git checkout main
git pull origin main
git branch -d "$BRANCH" 2>/dev/null || true
git remote prune origin 2>/dev/null || true
```

Mark `cleanup` completed.

---

## Phase 9 — Post summary + close issue

Mark `comment` in_progress.

```bash
gh issue comment "$ISSUE_NUMBER" --body "## claude-auto pipeline complete

**PR merged:** #${PR_NUMBER}
**Branch:** \`${BRANCH}\`
**Test iterations needed:** ${TEST_ITERATIONS}
**Review findings:**
${REVIEW_SUMMARY}

Changes are now on \`main\`. Closing issue."

gh issue close "$ISSUE_NUMBER" --reason completed
```

Mark `comment` completed.

---

## Failure Modes

| Phase | Failure | Action |
|-------|---------|--------|
| 2 | Tests never green after max iterations | Post failure comment, exit 1 |
| 4 | Diff too large + no label | Post comment, exit 1 |
| 6 | CI never green after 20 min | Post comment with run link, exit 1 |
| 7 | Admin merge rejected | Post comment with PR URL, exit 1 |
| Any | Unexpected exception | Workflow post-failure step posts comment |

The workflow's `post failure comment on error` step in `claude-auto.yml` catches any
unhandled exit to ensure the issue always gets a comment even if Claude crashes.

---

## Related Skills

- **stack-create**: Used internally for local dry-run mode
- **ci-watch**: Similar CI polling pattern (single-session use)
- **hawk**: Deep Go-specific review (this skill uses a generic reviewer instead)
- **stack-auto-pr-merge**: Simpler single-change auto-merge (no test loop, no review)
